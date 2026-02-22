#!/usr/bin/env python3
"""Render deterministic release notes for milestone or product releases.

Output follows docs/RELEASE_TEMPLATE.md structure. Set FROM_COMPOSER=1
to include the [from-composer] marker at the top.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _git_head_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent.parent.parent,
    )
    return proc.stdout.strip()


def _render(
    tag: str,
    main_sha: str,
    image_ref: str,
    archs: list[str],
    prs: list[str],
    receipts: list[str],
    from_composer: bool,
) -> str:
    lines: list[str] = []

    if from_composer:
        lines.append("[from-composer]")
        lines.append("")

    lines.append("## Context")
    lines.append(f"This release advances {tag}.")
    lines.append("")

    lines.append("## main HEAD")
    lines.append(f"- SHA: `{main_sha}`")
    lines.append("")

    lines.append("## IMAGE_REF (digest pinned)")
    lines.append(f"`{image_ref}`")
    lines.append("")
    arch_str = ", ".join(sorted(archs)) if archs else "<amd64, arm64>"
    lines.append(f"Architectures verified: `{arch_str}`")
    lines.append("")

    lines.append("## PRs included")
    for pr in prs:
        pr = pr.strip()
        if pr and not pr.startswith("#"):
            pr = f"#{pr}"
        if pr:
            lines.append(f"- {pr}")
    if not prs:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Operational Impact")
    lines.append("- (fill in bullet points)")
    lines.append("")

    lines.append("## Proof / Receipts")
    for r in receipts:
        r = r.strip()
        if r:
            lines.append(f"- {r}")
    if not receipts:
        lines.append("- (fill in paths)")
    lines.append("")

    lines.append("## Notes")
    lines.append("- (optional)")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--tag", required=True, help="Release tag (e.g. m19-20260222T201429Z)")
    parser.add_argument(
        "--main-sha",
        default=None,
        help="main HEAD SHA (default: git rev-parse HEAD)",
    )
    parser.add_argument(
        "--image-ref",
        required=True,
        help="Digest-pinned IMAGE_REF (e.g. account.dkr.ecr.region.amazonaws.com/repo@sha256:digest)",
    )
    parser.add_argument(
        "--arch",
        action="append",
        default=[],
        dest="archs",
        help="Architecture verified (repeatable; e.g. --arch amd64 --arch arm64)",
    )
    parser.add_argument(
        "--prs",
        default="",
        help="Comma-separated PR numbers (e.g. 213,214,215,216)",
    )
    parser.add_argument(
        "--receipts",
        action="append",
        default=[],
        help="Receipt path (repeatable)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write output to file instead of stdout",
    )
    args = parser.parse_args()

    main_sha = args.main_sha
    if main_sha is None:
        main_sha = _git_head_sha()

    pr_list: list[str] = [p.strip() for p in args.prs.split(",") if p.strip()]
    receipts = args.receipts
    from_composer = os.environ.get("FROM_COMPOSER", "").strip() in ("1", "true", "yes")

    out = _render(
        tag=args.tag,
        main_sha=main_sha,
        image_ref=args.image_ref,
        archs=args.archs,
        prs=pr_list,
        receipts=receipts,
        from_composer=from_composer,
    )

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    else:
        print(out, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
