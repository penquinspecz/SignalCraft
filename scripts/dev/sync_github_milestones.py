#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

DEFAULT_ROADMAP_PATH = Path("docs/ROADMAP.md")
BUCKET_MILESTONES = ("Infra & Tooling", "Docs & Governance", "Backlog Cleanup")
MILESTONE_TITLE_RE = re.compile(r"^M\d+$")
ROADMAP_MILESTONE_RE = re.compile(r"^##\s+Milestone\s+(\d+)([A-Z]?)\s+[—-]\s+")


class MilestoneSyncError(RuntimeError):
    """Raised when milestone sync cannot continue."""


def _run_gh_api(args: Sequence[str]) -> str:
    cmd = ["gh", "api", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise MilestoneSyncError(f"gh api failed ({' '.join(args)}): {stderr}")
    return proc.stdout


def _list_milestones() -> set[str]:
    titles: set[str] = set()
    page = 1
    while True:
        payload = _run_gh_api([f"repos/{{owner}}/{{repo}}/milestones?state=all&per_page=100&page={page}"])
        decoded = json.loads(payload)
        if not isinstance(decoded, list):
            raise MilestoneSyncError("unexpected milestone list response shape")
        if not decoded:
            return titles
        for item in decoded:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                titles.add(title.strip())
        page += 1


def _create_milestone(title: str) -> None:
    _run_gh_api(
        [
            "repos/{owner}/{repo}/milestones",
            "--method",
            "POST",
            "-f",
            f"title={title}",
            "-f",
            "state=open",
        ]
    )


def _dedupe_preserve_order(items: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _parse_roadmap_milestones(path: Path) -> tuple[list[str], list[str]]:
    if not path.exists():
        raise MilestoneSyncError(f"roadmap not found: {path}")

    numbers: set[int] = set()
    suffix_aliases: set[tuple[int, str]] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROADMAP_MILESTONE_RE.match(line.strip())
        if not match:
            continue
        number = int(match.group(1))
        suffix = match.group(2)
        numbers.add(number)
        if suffix:
            suffix_aliases.add((number, suffix))

    if not numbers:
        raise MilestoneSyncError(f"no roadmap milestone headings found in: {path}")

    roadmap_titles = [f"M{number}" for number in sorted(numbers)]
    alias_notes = [f"M{number}{suffix}->M{number}" for number, suffix in sorted(suffix_aliases)]
    return roadmap_titles, alias_notes


def _validate_explicit_milestones(raw_titles: Sequence[str]) -> list[str]:
    cleaned = _dedupe_preserve_order([title.strip() for title in raw_titles if title.strip()])
    if not cleaned:
        raise MilestoneSyncError("no non-empty milestone titles provided")

    invalid = [title for title in cleaned if not MILESTONE_TITLE_RE.fullmatch(title) and title not in BUCKET_MILESTONES]
    if invalid:
        invalid_text = ", ".join(invalid)
        raise MilestoneSyncError(
            f"invalid --milestone value(s): {invalid_text}. Allowed: M<digits> or bucket milestones."
        )
    return cleaned


def _join_or_none(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "(none)"


def _print_summary(
    *,
    mode: str,
    source: str,
    roadmap_path: Path | None,
    roadmap_milestones: Sequence[str],
    alias_notes: Sequence[str],
    targets: Sequence[str],
    created: Sequence[str],
    already_exists: Sequence[str],
    missing: Sequence[str],
) -> None:
    print("MILESTONE_SYNC_SUMMARY")
    print(f"mode: {mode}")
    print(f"source: {source}")
    if roadmap_path is not None:
        print(f"roadmap_path: {roadmap_path}")
        print(f"roadmap_extracted: {_join_or_none(roadmap_milestones)}")
        print(f"roadmap_suffix_mapping: {_join_or_none(alias_notes)}")
    print(f"targets: {_join_or_none(targets)}")
    print(f"created: {_join_or_none(created)}")
    print(f"already_exists: {_join_or_none(already_exists)}")
    print(f"missing: {_join_or_none(missing)}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure GitHub milestones exist and stay aligned with docs/ROADMAP.md."
    )
    parser.add_argument(
        "--milestone",
        action="append",
        default=[],
        help="Explicit milestone title to ensure (repeatable). When provided, ROADMAP parsing is skipped.",
    )
    parser.add_argument(
        "--roadmap",
        default=str(DEFAULT_ROADMAP_PATH),
        help="Roadmap file path used in default mode (default: docs/ROADMAP.md).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without mutating GitHub milestones.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Check milestone existence only; exit non-zero if any target is missing.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    roadmap_path = Path(args.roadmap)

    try:
        if args.milestone:
            source = "explicit"
            roadmap_milestones: list[str] = []
            alias_notes: list[str] = []
            targets = _validate_explicit_milestones(args.milestone)
            include_roadmap_path = None
        else:
            source = "roadmap+bucket"
            roadmap_milestones, alias_notes = _parse_roadmap_milestones(roadmap_path)
            targets = _dedupe_preserve_order([*roadmap_milestones, *BUCKET_MILESTONES])
            include_roadmap_path = roadmap_path

        existing = _list_milestones()
        created: list[str] = []
        already_exists: list[str] = []

        for title in targets:
            if title in existing:
                already_exists.append(title)
            else:
                created.append(title)

        missing = list(created)

        if args.verify_only:
            _print_summary(
                mode="verify-only",
                source=source,
                roadmap_path=include_roadmap_path,
                roadmap_milestones=roadmap_milestones,
                alias_notes=alias_notes,
                targets=targets,
                created=[],
                already_exists=already_exists,
                missing=missing,
            )
            if missing:
                print("MILESTONE_SYNC_VERIFY_FAILED", file=sys.stderr)
                return 1
            print("MILESTONE_SYNC_OK")
            return 0

        if args.dry_run:
            _print_summary(
                mode="dry-run",
                source=source,
                roadmap_path=include_roadmap_path,
                roadmap_milestones=roadmap_milestones,
                alias_notes=alias_notes,
                targets=targets,
                created=[],
                already_exists=already_exists,
                missing=missing,
            )
            print("MILESTONE_SYNC_DRY_RUN_OK")
            return 0

        created_now: list[str] = []
        for title in missing:
            try:
                _create_milestone(title)
                created_now.append(title)
            except MilestoneSyncError:
                # Safe idempotency guard for races.
                existing = _list_milestones()
                if title in existing:
                    already_exists.append(title)
                    continue
                raise

        _print_summary(
            mode="apply",
            source=source,
            roadmap_path=include_roadmap_path,
            roadmap_milestones=roadmap_milestones,
            alias_notes=alias_notes,
            targets=targets,
            created=created_now,
            already_exists=_dedupe_preserve_order(already_exists),
            missing=[],
        )
        print("MILESTONE_SYNC_OK")
        return 0
    except MilestoneSyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
