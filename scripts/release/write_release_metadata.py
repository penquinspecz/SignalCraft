#!/usr/bin/env python3
"""Write deterministic release metadata for an ECR image tag/digest."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _run_aws(args: list[str]) -> dict:
    cmd = ["aws", *args, "--output", "json"]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def _parse_repo(image_repo: str) -> tuple[str, str, str]:
    # 048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel -> (account, region, repo_name)
    parts = image_repo.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"invalid image repo: {image_repo}")
    host, repo_name = parts
    host_parts = host.split(".")
    if len(host_parts) < 6 or host_parts[1:4] != ["dkr", "ecr", host_parts[3]]:
        # fallback tolerant parsing for private ECR hostnames
        account_id = host_parts[0]
        region = host_parts[3] if len(host_parts) > 3 else "us-east-1"
    else:
        account_id = host_parts[0]
        region = host_parts[3]
    return account_id, region, repo_name


def _collect_arch_digests(manifest_json: dict) -> tuple[list[str], dict[str, str]]:
    manifests = manifest_json.get("manifests", [])
    arch_map: dict[str, str] = {}
    for item in manifests:
        platform = item.get("platform") or {}
        os_name = platform.get("os")
        arch = platform.get("architecture")
        digest = item.get("digest")
        if os_name == "linux" and arch and digest:
            arch_map[arch] = digest
    supported = sorted(arch_map.keys())
    return supported, arch_map


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image-repo", required=True)
    ap.add_argument("--image-tag", required=True)
    ap.add_argument("--image-digest", default="")
    ap.add_argument("--aws-region", default="")
    ap.add_argument("--git-sha", default="")
    ap.add_argument("--build-timestamp", default="")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    account_id, repo_region, repo_name = _parse_repo(args.image_repo)
    region = args.aws_region or repo_region

    image_digest = args.image_digest
    if not image_digest:
        details = _run_aws(
            [
                "ecr",
                "describe-images",
                "--region",
                region,
                "--repository-name",
                repo_name,
                "--image-ids",
                f"imageTag={args.image_tag}",
            ]
        )
        items = details.get("imageDetails") or []
        if not items:
            raise SystemExit(f"image not found for tag {args.image_tag}")
        image_digest = items[0].get("imageDigest", "")

    batch = _run_aws(
        [
            "ecr",
            "batch-get-image",
            "--region",
            region,
            "--repository-name",
            repo_name,
            "--image-ids",
            f"imageDigest={image_digest}",
            "--accepted-media-types",
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.index.v1+json",
        ]
    )
    images = batch.get("images") or []
    if not images:
        failures = batch.get("failures") or []
        raise SystemExit(f"unable to fetch manifest list: {failures}")

    image_manifest = images[0].get("imageManifest", "")
    manifest_json = json.loads(image_manifest)
    supported_architectures, arch_digests = _collect_arch_digests(manifest_json)

    metadata = {
        "schema_version": 1,
        "git_sha": args.git_sha,
        "image_repo": args.image_repo,
        "image_tag": args.image_tag,
        "image_digest": image_digest,
        "image_ref_digest": f"{args.image_repo}@{image_digest}",
        "build_timestamp": args.build_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "supported_architectures": supported_architectures,
        "arch_digests": arch_digests,
        "aws_region": region,
        "aws_account_id": account_id,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
