#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence

DEFAULT_MILESTONES = ("M22", "M23", "M24", "M25", "M26")


class MilestoneSyncError(RuntimeError):
    """Raised when gh api fails and milestone sync cannot proceed."""


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


def _normalize_targets(raw_targets: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in raw_targets:
        title = raw.strip()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(title)
    if not out:
        raise MilestoneSyncError("no non-empty milestone titles provided")
    return out


def _format_summary_line(name: str, values: Sequence[str]) -> str:
    rendered = ", ".join(values) if values else "(none)"
    return f"{name}: {rendered}"


def sync_milestones(targets: Sequence[str]) -> tuple[list[str], list[str]]:
    existing = _list_milestones()
    created: list[str] = []
    already_exists: list[str] = []

    for title in targets:
        if title in existing:
            already_exists.append(title)
            continue

        try:
            _create_milestone(title)
            created.append(title)
            existing.add(title)
        except MilestoneSyncError:
            # Handle races/idempotency safely: if it exists now, treat as already present.
            existing = _list_milestones()
            if title in existing:
                already_exists.append(title)
                continue
            raise

    return created, already_exists


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure roadmap GitHub milestones exist (create missing milestone titles)."
    )
    parser.add_argument(
        "--milestone",
        action="append",
        default=[],
        help="Milestone title to ensure exists (repeatable). Defaults to M22..M26 when omitted.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    raw_targets = args.milestone or list(DEFAULT_MILESTONES)

    try:
        targets = _normalize_targets(raw_targets)
        created, already_exists = sync_milestones(targets)
    except MilestoneSyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("MILESTONE_SYNC_OK")
    print(_format_summary_line("targets", targets))
    print(_format_summary_line("created", created))
    print(_format_summary_line("already_exists", already_exists))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
