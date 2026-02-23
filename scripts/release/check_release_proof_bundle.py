#!/usr/bin/env python3
"""Validate release proof bundle completeness (M19A).

Ensures release metadata artifact includes required fields and CI evidence.
Use when creating milestone releases to verify proof bundle is complete.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_KEYS = [
    "git_sha",
    "image_repo",
    "image_tag",
    "image_digest",
    "build_timestamp",
    "supported_architectures",
    "image_ref_digest",
]

# CI evidence keys (required when --require-ci-evidence)
CI_EVIDENCE_KEYS = ["ci_run_url", "ci_run_id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("metadata_path", type=Path, help="Path to release-*.json")
    ap.add_argument(
        "--require-ci-evidence",
        action="store_true",
        help="Require ci_run_url and ci_run_id (set when built in CI)",
    )
    args = ap.parse_args()

    path = args.metadata_path
    if not path.exists():
        print(f"FAIL: metadata not found: {path}", file=sys.stderr)
        return 1

    doc = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_KEYS if k not in doc]
    if missing:
        print(f"FAIL: missing required keys: {missing}", file=sys.stderr)
        return 1

    if not isinstance(doc.get("supported_architectures"), list) or not doc["supported_architectures"]:
        print("FAIL: supported_architectures must be a non-empty list", file=sys.stderr)
        return 1

    image_ref = str(doc.get("image_ref_digest", "")).strip()
    if not re.match(
        r"^\d+\.dkr\.ecr\.[^.]+\.amazonaws\.com\/[A-Za-z0-9._\/-]+@sha256:[0-9a-f]{64}$",
        image_ref,
    ):
        print(f"FAIL: invalid image_ref_digest format: {image_ref}", file=sys.stderr)
        return 1

    if args.require_ci_evidence:
        ci_missing = [k for k in CI_EVIDENCE_KEYS if k not in doc or not str(doc.get(k, "")).strip()]
        if ci_missing:
            print(
                f"FAIL: CI evidence required but missing: {ci_missing}. "
                "Release metadata from CI build includes ci_run_url and ci_run_id.",
                file=sys.stderr,
            )
            return 1

    print(f"PASS: release proof bundle valid image_ref_digest={image_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
