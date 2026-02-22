#!/usr/bin/env python3
"""Render deterministic release notes for milestone or product releases.

Output follows docs/RELEASE_NOTES_STYLE.md. Set FROM_COMPOSER=1
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


def _render_milestone(
    tag: str,
    main_sha: str,
    image_ref: str,
    archs: list[str],
    prs: list[str],
    receipts: list[str],
    why_bullets: list[str],
    from_composer: bool,
) -> str:
    """Milestone: proof-first, short rationale."""
    lines: list[str] = []

    if from_composer:
        lines.append("[from-composer]")
        lines.append("")

    lines.append("## Why this release exists")
    for b in why_bullets:
        b = b.strip()
        if b:
            lines.append(f"- {b}")
    if not why_bullets:
        lines.append("- (fill in 1–3 bullets)")
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
    for pr in sorted(prs):
        pr = pr.strip()
        if pr and not pr.startswith("#"):
            pr = f"#{pr}"
        if pr:
            lines.append(f"- {pr}")
    if not prs:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Proof / Receipts")
    for r in sorted(receipts):
        r = r.strip()
        if r:
            lines.append(f"- {r}")
    if not receipts:
        lines.append("- (fill in paths)")
    lines.append("")

    return "\n".join(lines)


def _render_product(
    tag: str,
    main_sha: str,
    image_ref: str | None,
    archs: list[str],
    prs: list[str],
    receipts: list[str],
    highlights: list[str],
    breaking: list[str],
    upgrade: list[str],
    known_issues: list[str],
    from_composer: bool,
) -> str:
    """Product: narrative + highlights + migration notes."""
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

    if image_ref:
        lines.append("## IMAGE_REF (digest pinned)")
        lines.append(f"`{image_ref}`")
        lines.append("")
        arch_str = ", ".join(sorted(archs)) if archs else "<amd64, arm64>"
        lines.append(f"Architectures verified: `{arch_str}`")
        lines.append("")

    lines.append("## Highlights")
    for h in highlights:
        h = h.strip()
        if h:
            lines.append(f"- {h}")
    if not highlights:
        lines.append("- (fill in)")
    lines.append("")

    lines.append("## Breaking changes")
    for b in breaking:
        b = b.strip()
        if b:
            lines.append(f"- {b}")
    if not breaking:
        lines.append("- None")
    lines.append("")

    lines.append("## Upgrade notes")
    for u in upgrade:
        u = u.strip()
        if u:
            lines.append(f"- {u}")
    if not upgrade:
        lines.append("- (fill in if applicable)")
    lines.append("")

    lines.append("## Known issues")
    for k in known_issues:
        k = k.strip()
        if k:
            lines.append(f"- {k}")
    if not known_issues:
        lines.append("- None")
    lines.append("")

    lines.append("## PRs included")
    for pr in sorted(prs):
        pr = pr.strip()
        if pr and not pr.startswith("#"):
            pr = f"#{pr}"
        if pr:
            lines.append(f"- {pr}")
    if not prs:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Proof / Receipts")
    for r in sorted(receipts):
        r = r.strip()
        if r:
            lines.append(f"- {r}")
    if not receipts:
        lines.append("- (fill in paths)")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--tag", required=True, help="Release tag (e.g. m19-20260222T201429Z or v0.2.0)")
    parser.add_argument(
        "--release-kind",
        choices=["milestone", "product"],
        default="milestone",
        help="Release kind (default: milestone)",
    )
    parser.add_argument(
        "--main-sha",
        default=None,
        help="main HEAD SHA (default: git rev-parse HEAD)",
    )
    parser.add_argument(
        "--image-ref",
        default=None,
        help="Digest-pinned IMAGE_REF (required for milestone; optional for product)",
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
        "--why",
        action="append",
        default=[],
        dest="why_bullets",
        help="Why this release exists (milestone only; repeatable)",
    )
    parser.add_argument(
        "--highlights",
        action="append",
        default=[],
        help="Highlight (product only; repeatable)",
    )
    parser.add_argument(
        "--breaking",
        action="append",
        default=[],
        help="Breaking change (product only; repeatable)",
    )
    parser.add_argument(
        "--upgrade",
        action="append",
        default=[],
        help="Upgrade note (product only; repeatable)",
    )
    parser.add_argument(
        "--known-issues",
        action="append",
        default=[],
        dest="known_issues",
        help="Known issue (product only; repeatable)",
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

    if args.release_kind == "milestone":
        if not args.image_ref:
            parser.error("--image-ref is required for milestone releases")
        out = _render_milestone(
            tag=args.tag,
            main_sha=main_sha,
            image_ref=args.image_ref,
            archs=args.archs,
            prs=pr_list,
            receipts=receipts,
            why_bullets=args.why_bullets,
            from_composer=from_composer,
        )
    else:
        out = _render_product(
            tag=args.tag,
            main_sha=main_sha,
            image_ref=args.image_ref,
            archs=args.archs,
            prs=pr_list,
            receipts=receipts,
            highlights=args.highlights,
            breaking=args.breaking,
            upgrade=args.upgrade,
            known_issues=args.known_issues,
            from_composer=from_composer,
        )

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    else:
        print(out, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
