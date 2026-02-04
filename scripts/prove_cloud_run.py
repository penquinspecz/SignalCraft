#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

RUN_ID_REGEX = re.compile(r"jobintel start\s+([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z)")
RUN_ID_KV_REGEX = re.compile(r"^JOBINTEL_RUN_ID=([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z)$", re.MULTILINE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _state_dir() -> Path:
    return Path(os.environ.get("JOBINTEL_STATE_DIR", _repo_root() / "state"))


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _extract_run_id(logs: str) -> Optional[str]:
    match = RUN_ID_KV_REGEX.search(logs)
    if match:
        return match.group(1)
    match = RUN_ID_REGEX.search(logs)
    if not match:
        return None
    return match.group(1)


def _kubectl_logs(namespace: str, job_name: str, kube_context: Optional[str]) -> str:
    cmd = ["kubectl", "logs", f"job/{job_name}", "-n", namespace]
    if kube_context:
        cmd.extend(["--context", kube_context])
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "kubectl logs failed")
    return result.stdout


def _commit_sha() -> Optional[str]:
    result = _run(["git", "rev-parse", "HEAD"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _verify(bucket: str, prefix: str, run_id: str) -> int:
    cmd = [
        sys.executable,
        str(_repo_root() / "scripts" / "verify_published_s3.py"),
        "--bucket",
        bucket,
        "--run-id",
        run_id,
        "--prefix",
        prefix,
        "--verify-latest",
    ]
    result = _run(cmd)
    return result.returncode


def _print_next_commands(run_id: str, bucket: str, prefix: str, namespace: str, job_name: str) -> None:
    lines = [
        "Next commands:",
        f"  python scripts/verify_published_s3.py --bucket {bucket} --run-id {run_id} --prefix {prefix} --verify-latest",
        f"  cat state/proofs/{run_id}.json",
        f"  kubectl -n {namespace} logs job/{job_name}",
    ]
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture proof artifacts for a real cloud run.")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="jobintel")
    parser.add_argument("--namespace", default="jobintel")
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--kube-context", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    try:
        run_id = args.run_id
        if not run_id:
            logs = _kubectl_logs(args.namespace, args.job_name, args.kube_context)
            run_id = _extract_run_id(logs)
        if not run_id:
            print("ERROR: run_id not provided and could not be extracted from logs", file=sys.stderr)
            return 3

        verify_code = _verify(args.bucket, args.prefix, run_id)
        verified_ok = verify_code == 0
        proof = {
            "run_id": run_id,
            "cluster_context": args.kube_context,
            "namespace": args.namespace,
            "job_name": args.job_name,
            "bucket": args.bucket,
            "prefix": args.prefix,
            "verified_ok": verified_ok,
            "timestamp_utc": _utc_now_iso(),
            "commit_sha": _commit_sha(),
        }

        proof_dir = _state_dir() / "proofs"
        proof_dir.mkdir(parents=True, exist_ok=True)
        proof_path = proof_dir / f"{run_id}.json"
        proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        if verify_code != 0:
            print("ERROR: verify_published_s3 failed", file=sys.stderr)
            return 2
        _print_next_commands(run_id, args.bucket, args.prefix, args.namespace, args.job_name)
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"ERROR: {exc!r}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
