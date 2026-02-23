#!/usr/bin/env python3
"""Assert IMAGE_REF is digest-pinned for non-dev DR/operator paths.

M19A: Non-dev deployment paths default to digest pinning (tag opt-in for dev only).
If IMAGE_REF is a tag (no @sha256:), require explicit --allow-tag or DEV_MODE=1.
"""

from __future__ import annotations

import argparse
import os
import sys


def is_digest_pinned(ref: str) -> bool:
    """True if ref contains @sha256: (digest-pinned format)."""
    return bool(ref and "@sha256:" in ref)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image_ref", nargs="?", default="", help="IMAGE_REF to check")
    ap.add_argument("--allow-tag", action="store_true", help="Allow tag for dev iteration")
    ap.add_argument("--context", default="", help="Context for error message (e.g. dr_drill)")
    args = ap.parse_args()

    ref = (args.image_ref or os.environ.get("IMAGE_REF", "")).strip()
    allow_tag = args.allow_tag or os.environ.get("DEV_MODE", "").strip().lower() in ("1", "true", "yes")

    if not ref:
        return 0  # No ref to check

    if is_digest_pinned(ref):
        return 0

    if allow_tag:
        print(f"[INFO] DEV_MODE/--allow-tag: allowing tag ref in {args.context or 'operator path'}", file=sys.stderr)
        return 0

    ctx = f" ({args.context})" if args.context else ""
    print(
        f"[FAIL] IMAGE_REF must be digest-pinned (repo@sha256:<digest>) for non-dev paths.{ctx}\n"
        f"  Got: {ref}\n"
        f"  Use --allow-tag or DEV_MODE=1 for development iteration only.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
