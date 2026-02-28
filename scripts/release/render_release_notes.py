#!/usr/bin/env python3
"""Render self-contained release notes for milestone or product releases."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DIGEST_RE = re.compile(r"@(?P<digest>sha256:[0-9a-f]{64})$")
SEMVER_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def _git_head_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent.parent.parent,
    )
    return proc.stdout.strip()


def _clean(values: list[str]) -> list[str]:
    return [v.strip() for v in values if v and v.strip()]


def _extract_digest(image_ref: str | None) -> str | None:
    if not image_ref:
        return None
    match = DIGEST_RE.search(image_ref.strip())
    if not match:
        return None
    return match.group("digest")


def _normalize_semver_level(tag: str, semver_level: str) -> str:
    if semver_level in {"major", "minor", "patch"}:
        return semver_level

    match = SEMVER_RE.match(tag)
    if not match:
        return "minor"

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))

    if major > 0 and minor == 0 and patch == 0:
        return "major"
    if patch > 0:
        return "patch"
    return "minor"


def _render_images_block(image_ref: str | None, archs: list[str]) -> list[str]:
    lines: list[str] = []
    digest = _extract_digest(image_ref)
    if image_ref:
        lines.append(f"- IMAGE_REF: `{image_ref}`")
    else:
        lines.append("- IMAGE_REF: Not recorded at tag time")

    if digest:
        lines.append(f"- Digest: `{digest}`")
    else:
        lines.append("- Digest: Not recorded at tag time")

    arch_str = ", ".join(sorted(archs)) if archs else "Not recorded at tag time"
    lines.append(f"- Architectures: `{arch_str}`" if archs else "- Architectures: Not recorded at tag time")
    return lines


def _render_product(
    *,
    tag: str,
    semver_level: str,
    main_sha: str,
    image_ref: str | None,
    archs: list[str],
    highlights: list[str],
    proven: list[str],
    upgrade_notes: list[str],
    added: list[str],
    changed: list[str],
    fixed: list[str],
    breaking: list[str],
    known_issues: list[str],
    proof_refs: list[str],
    why: list[str],
    migration: list[str],
    compatibility: list[str],
    deprecations: list[str],
    ci_workflow: str | None,
    ci_run_id: str | None,
    ci_run_url: str | None,
) -> str:
    lines: list[str] = []

    lines.append(f"# SignalCraft Product Release {tag}")
    lines.append("")

    lines.append("## Highlights")
    for item in highlights:
        lines.append(f"- {item}")
    if not highlights:
        lines.append("- None")
    lines.append("")

    lines.append("## What's Proven (Operator Reality Check)")
    for item in proven:
        lines.append(f"- {item}")
    if not proven:
        lines.append("- None")
    lines.append("")

    lines.append("## Images (Digest-pinned)")
    lines.extend(_render_images_block(image_ref, archs))
    lines.append("")

    lines.append("## Upgrade / Operational Notes")
    for item in upgrade_notes:
        lines.append(f"- {item}")
    if not upgrade_notes:
        lines.append("- None")
    lines.append("")

    lines.append("## Changes (categorized)")
    lines.append("- Added:")
    if added:
        for item in added:
            lines.append(f"  - {item}")
    else:
        lines.append("  - None")
    lines.append("- Changed:")
    if changed:
        for item in changed:
            lines.append(f"  - {item}")
    else:
        lines.append("  - None")
    lines.append("- Fixed:")
    if fixed:
        for item in fixed:
            lines.append(f"  - {item}")
    else:
        lines.append("  - None")
    lines.append("")

    lines.append("## Breaking Changes")
    for item in breaking:
        lines.append(f"- {item}")
    if not breaking:
        lines.append("- None")
    lines.append("")

    lines.append("## Known Issues")
    for item in known_issues:
        lines.append(f"- {item}")
    if not known_issues:
        lines.append("- None")
    lines.append("")

    lines.append("## Proof References")
    for item in proof_refs:
        lines.append(f"- {item}")
    if not proof_refs:
        lines.append("- None")
    lines.append("")

    if semver_level == "major":
        lines.append("## Why this release exists")
        for item in why:
            lines.append(f"- {item}")
        if not why:
            lines.append("- None")
        lines.append("")

        lines.append("## Migration / Upgrade Guide")
        for item in migration:
            lines.append(f"- {item}")
        if not migration:
            lines.append("- None")
        lines.append("")

        lines.append("## Compatibility Matrix")
        for item in compatibility:
            lines.append(f"- {item}")
        if not compatibility:
            lines.append("- None")
        lines.append("")

        lines.append("## Deprecations Timeline")
        for item in deprecations:
            lines.append(f"- {item}")
        if not deprecations:
            lines.append("- None")
        lines.append("")

    digest = _extract_digest(image_ref)
    lines.append("## Integrity")
    lines.append(f"- Main commit SHA: `{main_sha}`")
    lines.append(f"- IMAGE_REF digest: `{digest}`" if digest else "- IMAGE_REF digest: Not recorded at tag time")
    lines.append(f"- CI workflow URL: `{ci_run_url}`" if ci_run_url else "- CI workflow URL: Not recorded at tag time")
    lines.append(f"- CI run ID: `{ci_run_id}`" if ci_run_id else "- CI run ID: Not recorded at tag time")
    lines.append(f"- CI workflow: `{ci_workflow}`" if ci_workflow else "- CI workflow: Not recorded at tag time")
    lines.append("")

    return "\n".join(lines)


def _render_milestone(
    *,
    tag: str,
    main_sha: str,
    image_ref: str | None,
    archs: list[str],
    milestone_context: list[str],
    exercised: list[str],
    execution_arn: str | None,
    terminal_state: str | None,
    terminal_status: str | None,
    receipts_root: str | None,
    guardrail_checks: list[str],
    outcomes: list[str],
    next_steps: list[str],
    proof_refs: list[str],
) -> str:
    lines: list[str] = []

    lines.append(f"# SignalCraft Milestone Release {tag}")
    lines.append("")

    lines.append("## Milestone Context")
    lines.append(f"- milestone_tag: `{tag}`")
    lines.append(f"- Main commit SHA: `{main_sha}`")
    for item in milestone_context:
        lines.append(f"- {item}")
    if not milestone_context:
        lines.append("- None")
    lines.append("")

    lines.append("## What was exercised")
    for item in exercised:
        lines.append(f"- {item}")
    if not exercised:
        lines.append("- None")
    lines.append("")

    lines.append("## Execution Evidence")
    lines.append(f"- execution_arn: `{execution_arn}`" if execution_arn else "- execution_arn: Not recorded at tag time")
    lines.append(f"- terminal_state: `{terminal_state}`" if terminal_state else "- terminal_state: Not recorded at tag time")
    lines.append(f"- terminal_status: `{terminal_status}`" if terminal_status else "- terminal_status: Not recorded at tag time")
    lines.append(f"- receipts_root: `{receipts_root}`" if receipts_root else "- receipts_root: Not recorded at tag time")
    lines.append("")

    lines.append("## Images (Digest-pinned)")
    lines.extend(_render_images_block(image_ref, archs))
    lines.append("")

    lines.append("## Guardrails/Determinism checks")
    for item in guardrail_checks:
        lines.append(f"- {item}")
    if not guardrail_checks:
        lines.append("- None")
    lines.append("")

    lines.append("## Outcome + Next steps")
    for item in outcomes:
        lines.append(f"- outcome: {item}")
    if not outcomes:
        lines.append("- outcome: None")
    for item in next_steps:
        lines.append(f"- next_step: {item}")
    if not next_steps:
        lines.append("- next_step: None")
    lines.append("")

    lines.append("## Proof References")
    for item in proof_refs:
        lines.append(f"- {item}")
    if not proof_refs:
        lines.append("- None")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--release-kind", choices=["product", "milestone"], default="milestone")
    parser.add_argument("--semver-level", choices=["auto", "major", "minor", "patch"], default="auto")
    parser.add_argument("--main-sha", default=None)
    parser.add_argument("--image-ref", default=None)
    parser.add_argument("--arch", action="append", default=[], dest="archs")
    parser.add_argument("--receipts", action="append", default=[])

    parser.add_argument("--highlights", action="append", default=[])
    parser.add_argument("--proven", action="append", default=[])
    parser.add_argument("--upgrade-note", action="append", default=[], dest="upgrade_notes")
    parser.add_argument("--change-added", action="append", default=[])
    parser.add_argument("--change-changed", action="append", default=[])
    parser.add_argument("--change-fixed", action="append", default=[])
    parser.add_argument("--breaking", action="append", default=[])
    parser.add_argument("--known-issues", action="append", default=[], dest="known_issues")

    parser.add_argument("--why", action="append", default=[])
    parser.add_argument("--migration", action="append", default=[])
    parser.add_argument("--compatibility", action="append", default=[])
    parser.add_argument("--deprecations", action="append", default=[])

    parser.add_argument("--milestone-context", action="append", default=[])
    parser.add_argument("--exercised", action="append", default=[])
    parser.add_argument("--execution-arn", default=None)
    parser.add_argument("--terminal-state", default=None)
    parser.add_argument("--terminal-status", default=None)
    parser.add_argument("--receipts-root", default=None)
    parser.add_argument("--guardrail-check", action="append", default=[])
    parser.add_argument("--outcome", action="append", default=[])
    parser.add_argument("--next-step", action="append", default=[])

    parser.add_argument("--ci-workflow", default=None)
    parser.add_argument("--ci-run-id", default=None)
    parser.add_argument("--ci-run-url", default=None)

    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    main_sha = args.main_sha or _git_head_sha()

    receipts = _clean(args.receipts)
    archs = _clean(args.archs)

    if args.release_kind == "product":
        semver_level = _normalize_semver_level(args.tag, args.semver_level)
        out = _render_product(
            tag=args.tag,
            semver_level=semver_level,
            main_sha=main_sha,
            image_ref=args.image_ref,
            archs=archs,
            highlights=_clean(args.highlights),
            proven=_clean(args.proven),
            upgrade_notes=_clean(args.upgrade_notes),
            added=_clean(args.change_added),
            changed=_clean(args.change_changed),
            fixed=_clean(args.change_fixed),
            breaking=_clean(args.breaking),
            known_issues=_clean(args.known_issues),
            proof_refs=receipts,
            why=_clean(args.why),
            migration=_clean(args.migration),
            compatibility=_clean(args.compatibility),
            deprecations=_clean(args.deprecations),
            ci_workflow=args.ci_workflow,
            ci_run_id=args.ci_run_id,
            ci_run_url=args.ci_run_url,
        )
    else:
        out = _render_milestone(
            tag=args.tag,
            main_sha=main_sha,
            image_ref=args.image_ref,
            archs=archs,
            milestone_context=_clean(args.milestone_context),
            exercised=_clean(args.exercised),
            execution_arn=args.execution_arn,
            terminal_state=args.terminal_state,
            terminal_status=args.terminal_status,
            receipts_root=args.receipts_root,
            guardrail_checks=_clean(args.guardrail_check),
            outcomes=_clean(args.outcome),
            next_steps=_clean(args.next_step),
            proof_refs=receipts,
        )

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    else:
        print(out, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
