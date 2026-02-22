#!/usr/bin/env python3
"""Fail if an ECR image ref is missing required architectures."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass


@dataclass
class ImageRef:
    image_repo: str
    repository_name: str
    region: str
    tag: str = ""
    digest: str = ""


def _run_aws(args: list[str]) -> dict:
    proc = subprocess.run(["aws", *args, "--output", "json"], check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def _parse_image_ref(ref: str, default_region: str) -> ImageRef:
    if "@sha256:" in ref:
        image_repo, digest = ref.split("@", 1)
        tag = ""
    else:
        image_repo, tag = ref.rsplit(":", 1)
        digest = ""

    host, repository_name = image_repo.split("/", 1)
    m = re.match(r"^(?P<acct>\d+)\.dkr\.ecr\.(?P<region>[^.]+)\.amazonaws\.com$", host)
    if not m:
        raise SystemExit(f"unsupported image host for ECR: {host}")
    region = m.group("region") or default_region
    return ImageRef(image_repo=image_repo, repository_name=repository_name, region=region, tag=tag, digest=digest)


def _resolve_digest(ref: ImageRef) -> str:
    if ref.digest:
        return ref.digest
    data = _run_aws(
        [
            "ecr",
            "describe-images",
            "--region",
            ref.region,
            "--repository-name",
            ref.repository_name,
            "--image-ids",
            f"imageTag={ref.tag}",
        ]
    )
    details = data.get("imageDetails") or []
    if not details:
        raise SystemExit(f"image tag not found: {ref.image_repo}:{ref.tag}")
    digest = details[0].get("imageDigest", "")
    if not digest:
        raise SystemExit("image digest missing in describe-images response")
    return digest


def _supported_arches(ref: ImageRef, digest: str) -> list[str]:
    data = _run_aws(
        [
            "ecr",
            "batch-get-image",
            "--region",
            ref.region,
            "--repository-name",
            ref.repository_name,
            "--image-ids",
            f"imageDigest={digest}",
            "--accepted-media-types",
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.index.v1+json",
        ]
    )
    images = data.get("images") or []
    if not images:
        raise SystemExit(f"manifest list unavailable: {data.get('failures')}")
    manifest = json.loads(images[0]["imageManifest"])
    manifests = manifest.get("manifests") or []
    out: set[str] = set()
    for item in manifests:
        plat = item.get("platform") or {}
        if plat.get("os") == "linux" and plat.get("architecture"):
            out.add(plat["architecture"])
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image-ref", required=True, help="<repo>:<tag> or <repo>@sha256:<digest>")
    ap.add_argument("--require-arch", action="append", default=[], help="required architecture; repeatable")
    ap.add_argument("--aws-region", default="us-east-1")
    args = ap.parse_args()

    required = args.require_arch or ["amd64", "arm64"]
    ref = _parse_image_ref(args.image_ref, args.aws_region)
    digest = _resolve_digest(ref)
    arches = _supported_arches(ref, digest)

    missing = [a for a in required if a not in arches]
    if missing:
        raise SystemExit(
            f"missing required architectures {missing} for {args.image_ref} (digest={digest}, found={arches})"
        )

    print(json.dumps({"image_ref": args.image_ref, "digest": digest, "architectures": arches}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
