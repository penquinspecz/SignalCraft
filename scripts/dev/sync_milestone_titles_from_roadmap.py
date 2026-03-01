#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_ROADMAP_PATH = Path("docs/ROADMAP.md")
TOP_HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*$")
MILESTONE_HEADING_RE = re.compile(r"^\s*#{2,6}\s+Milestone\s+(\d+)([A-Za-z]?)\s+[—-]\s+(.+?)\s*$")
STATUS_GLYPH_RE = re.compile(r"\s+[✅◐⏸].*$")
MANAGED_TITLE_RE = re.compile(r"^M(\d+)(?:\s+—\s+.+)?$")


class TitleSyncError(RuntimeError):
    """Raised when milestone title sync cannot continue."""


@dataclass(frozen=True)
class RoadmapCandidate:
    key: str
    number: int
    suffix: str
    title: str
    section: str
    heading_line: int


@dataclass(frozen=True)
class MilestoneRow:
    number: int
    title: str
    state: str


@dataclass(frozen=True)
class RoadmapConflict:
    key: str
    chosen_title: str
    alternatives: tuple[str, ...]


def _run(cmd: Sequence[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, input=input_text)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "(no stderr)"
        raise TitleSyncError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    return proc.stdout


def _resolve_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo.strip()
    remote_url = _run(["git", "config", "--get", "remote.origin.url"]).strip()
    if not remote_url:
        raise TitleSyncError("could not resolve repository from git remote.origin.url")
    https_match = re.match(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    ssh_match = re.match(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    match = https_match or ssh_match
    if not match:
        raise TitleSyncError(f"unsupported GitHub remote URL format: {remote_url}")
    return f"{match.group('owner')}/{match.group('repo')}"


def _gh_api_json(path: str, *, method: str = "GET", payload: dict[str, object] | None = None) -> object:
    cmd = ["gh", "api", path]
    if method != "GET":
        cmd.extend(["--method", method])
    input_text = None
    if payload is not None:
        cmd.extend(["--input", "-"])
        input_text = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    raw = _run(cmd, input_text=input_text).strip()
    if not raw:
        return {}
    return json.loads(raw)


def _list_paginated(path: str) -> list[dict[str, object]]:
    page = 1
    out: list[dict[str, object]] = []
    while True:
        endpoint = f"{path}&page={page}" if "?" in path else f"{path}?page={page}"
        payload = _gh_api_json(endpoint)
        if not isinstance(payload, list):
            raise TitleSyncError(f"unexpected paginated response for {path}")
        if not payload:
            return out
        out.extend(item for item in payload if isinstance(item, dict))
        page += 1


def _clean_heading_title(raw: str) -> str:
    title = raw.strip()
    title = STATUS_GLYPH_RE.sub("", title).strip()
    return title


def _suffix_priority(number: int, suffix: str) -> int:
    normalized = suffix.upper()
    if number == 19:
        if normalized == "C":
            return 40
        if normalized == "B":
            return 30
        if normalized == "A":
            return 20
        return 10
    if normalized:
        return 20
    return 10


def _parse_roadmap(path: Path) -> tuple[dict[str, str], list[str], list[RoadmapConflict]]:
    if not path.exists():
        raise TitleSyncError(f"roadmap not found: {path}")

    section = ""
    candidates_by_key: dict[str, list[RoadmapCandidate]] = defaultdict(list)
    lines = path.read_text(encoding="utf-8").splitlines()

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        top_match = TOP_HEADING_RE.match(stripped)
        if top_match:
            heading = top_match.group(1).lower()
            if "active roadmap" in heading:
                section = "active"
            elif "parked" in heading:
                section = "parked"
            elif "archive" in heading:
                section = "archive"
            else:
                section = ""

        milestone_match = MILESTONE_HEADING_RE.match(stripped)
        if not milestone_match:
            continue
        if section not in {"active", "parked", "archive"}:
            continue

        number = int(milestone_match.group(1))
        suffix = milestone_match.group(2).upper()
        key = f"M{number}"
        raw_title = milestone_match.group(3)
        clean_title = _clean_heading_title(raw_title)
        if not clean_title:
            continue
        candidates_by_key[key].append(
            RoadmapCandidate(
                key=key,
                number=number,
                suffix=suffix,
                title=clean_title,
                section=section,
                heading_line=idx,
            )
        )

    if not candidates_by_key:
        raise TitleSyncError(f"no roadmap milestone headings found in: {path}")

    chosen_titles: dict[str, str] = {}
    notes: list[str] = []
    conflicts: list[RoadmapConflict] = []

    for key in sorted(candidates_by_key, key=lambda k: int(k[1:])):
        items = sorted(
            candidates_by_key[key],
            key=lambda c: (-_suffix_priority(c.number, c.suffix), c.heading_line),
        )
        chosen = items[0]
        chosen_titles[key] = chosen.title
        if chosen.number == 19 and chosen.suffix in {"A", "B", "C"}:
            notes.append(f"{key}: preferred 19{chosen.suffix} heading")

        unique_titles = sorted({item.title for item in items})
        if len(unique_titles) > 1:
            conflicts.append(
                RoadmapConflict(
                    key=key,
                    chosen_title=chosen.title,
                    alternatives=tuple(unique_titles),
                )
            )

    return chosen_titles, notes, conflicts


def _list_github_milestones(repo_slug: str) -> list[MilestoneRow]:
    rows = _list_paginated(f"repos/{repo_slug}/milestones?state=all&per_page=100")
    out: list[MilestoneRow] = []
    for row in rows:
        title = row.get("title")
        number = row.get("number")
        state = row.get("state")
        if not isinstance(title, str) or not title.strip() or not isinstance(number, int):
            continue
        out.append(MilestoneRow(number=number, title=title.strip(), state=state if isinstance(state, str) else "open"))
    return out


def _milestone_key_from_title(title: str) -> str | None:
    match = MANAGED_TITLE_RE.fullmatch(title.strip())
    if not match:
        return None
    return f"M{int(match.group(1))}"


def _desired_title(key: str, roadmap_title: str) -> str:
    return f"{key} — {roadmap_title.strip()}"


def _patch_milestone_title(repo_slug: str, milestone_number: int, title: str) -> None:
    _gh_api_json(
        f"repos/{repo_slug}/milestones/{milestone_number}",
        method="PATCH",
        payload={"title": title},
    )


def _print_report(
    *,
    mode: str,
    repo_slug: str,
    roadmap_path: Path,
    considered: int,
    renamed: list[str],
    already_ok: list[str],
    skipped_no_roadmap: list[str],
    missing_in_github: list[str],
    conflicts: list[str],
    notes: list[str],
) -> None:
    print("MILESTONE_TITLE_SYNC_SUMMARY")
    print(f"mode: {mode}")
    print(f"repo: {repo_slug}")
    print(f"roadmap: {roadmap_path}")
    print(f"total_considered: {considered}")
    print(f"renamed_count: {len(renamed)}")
    print(f"already_ok_count: {len(already_ok)}")
    print(f"skipped_no_roadmap_match_count: {len(skipped_no_roadmap)}")
    print(f"missing_in_github_count: {len(missing_in_github)}")
    print(f"conflicts_count: {len(conflicts)}")

    def _emit(label: str, items: list[str]) -> None:
        print(f"{label}: {', '.join(items) if items else '(none)'}")

    _emit("renamed", renamed)
    _emit("already_ok", already_ok)
    _emit("skipped_no_roadmap_match", skipped_no_roadmap)
    _emit("missing_in_github", missing_in_github)
    _emit("conflicts", conflicts)
    _emit("mapping_notes", notes)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename GitHub roadmap milestones to human-readable titles sourced from docs/ROADMAP.md."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print planned milestone title changes (default mode).")
    mode.add_argument("--apply", action="store_true", help="Apply milestone title renames via GitHub API.")
    mode.add_argument("--verify", action="store_true", help="Verify GitHub milestone titles match roadmap mapping.")
    parser.add_argument("--repo", default=None, help="GitHub repository slug (<owner>/<repo>).")
    parser.add_argument("--roadmap", default=str(DEFAULT_ROADMAP_PATH), help="Roadmap path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "dry-run"
    if args.apply:
        mode = "apply"
    elif args.verify:
        mode = "verify"

    roadmap_path = Path(args.roadmap)

    try:
        repo_slug = _resolve_repo_slug(args.repo)
        roadmap_titles, notes, roadmap_conflicts = _parse_roadmap(roadmap_path)
        gh_rows = _list_github_milestones(repo_slug)

        gh_keyed: dict[str, list[MilestoneRow]] = defaultdict(list)
        skipped_no_roadmap: list[str] = []
        for row in gh_rows:
            key = _milestone_key_from_title(row.title)
            if key is None:
                continue
            gh_keyed[key].append(row)

        roadmap_keys = set(roadmap_titles)
        gh_keys = set(gh_keyed)
        missing_in_github = [key for key in sorted(roadmap_keys, key=lambda x: int(x[1:])) if key not in gh_keys]

        conflicts: list[str] = []
        for conflict in roadmap_conflicts:
            conflicts.append(f"roadmap:{conflict.key}")

        renamed: list[str] = []
        already_ok: list[str] = []
        considered = 0
        verify_failures: list[str] = []

        for key in sorted(gh_keyed, key=lambda x: int(x[1:])):
            rows = gh_keyed[key]
            if len(rows) > 1:
                conflicts.append(f"github:{key}")
                continue

            row = rows[0]
            considered += 1
            roadmap_title = roadmap_titles.get(key)
            if roadmap_title is None:
                skipped_no_roadmap.append(key)
                continue

            desired = _desired_title(key, roadmap_title)
            if row.title == desired:
                already_ok.append(key)
                continue

            if mode == "verify":
                verify_failures.append(f"{key}: expected '{desired}' got '{row.title}'")
                continue

            if mode == "apply":
                _patch_milestone_title(repo_slug, row.number, desired)
            renamed.append(f"{key} -> {desired}")

        if mode == "apply":
            refreshed = _list_github_milestones(repo_slug)
            refreshed_keyed: dict[str, list[MilestoneRow]] = defaultdict(list)
            for row in refreshed:
                key = _milestone_key_from_title(row.title)
                if key is None:
                    continue
                refreshed_keyed[key].append(row)
            refreshed_by_key: dict[str, MilestoneRow] = {}
            for key, rows in refreshed_keyed.items():
                if len(rows) > 1:
                    conflicts.append(f"github:{key}")
                    continue
                refreshed_by_key[key] = rows[0]
            for key in sorted(roadmap_keys, key=lambda x: int(x[1:])):
                if key not in refreshed_by_key:
                    continue
                desired = _desired_title(key, roadmap_titles[key])
                actual = refreshed_by_key[key].title
                if actual != desired:
                    verify_failures.append(f"{key}: expected '{desired}' got '{actual}'")

        _print_report(
            mode=mode,
            repo_slug=repo_slug,
            roadmap_path=roadmap_path,
            considered=considered,
            renamed=renamed,
            already_ok=already_ok,
            skipped_no_roadmap=skipped_no_roadmap,
            missing_in_github=missing_in_github,
            conflicts=sorted(set(conflicts)),
            notes=notes,
        )

        if verify_failures:
            print("verify_failures:")
            for failure in verify_failures:
                print(f"  - {failure}")
            print("MILESTONE_TITLE_SYNC_VERIFY_FAILED", file=sys.stderr)
            return 1

        print("MILESTONE_TITLE_SYNC_OK")
        return 0
    except TitleSyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
