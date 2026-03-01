#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

BUCKET_MILESTONES = ("Infra & Tooling", "Docs & Governance", "Backlog Cleanup")
ROADMAP_HEADING_RE = re.compile(r"^##\s+Milestone\s+(?P<number>\d+)(?P<suffix>[A-Za-z]?)\b")


class CliError(RuntimeError):
    """Raised when `gh api` or repo resolution fails."""


def _run(cmd: Sequence[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, input=input_text)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "(no stderr)"
        raise CliError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    return proc.stdout


def _resolve_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo.strip()

    remote_url = _run(["git", "config", "--get", "remote.origin.url"]).strip()
    if not remote_url:
        raise CliError("could not resolve repository from git remote.origin.url")

    https_match = re.match(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    ssh_match = re.match(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    match = https_match or ssh_match
    if not match:
        raise CliError(f"unsupported GitHub remote URL format: {remote_url}")
    return f"{match.group('owner')}/{match.group('repo')}"


def _gh_api_json(repo_slug: str, path: str, *, method: str = "GET", payload: object | None = None) -> object:
    cmd = ["gh", "api", f"repos/{repo_slug}/{path}"]
    if method != "GET":
        cmd.extend(["--method", method])
    input_text = None
    if payload is not None:
        cmd.extend(["--input", "-"])
        input_text = json.dumps(payload, separators=(",", ":"))

    raw = _run(cmd, input_text=input_text).strip()
    if not raw:
        return {}
    return json.loads(raw)


def _list_milestones(repo_slug: str) -> list[dict[str, object]]:
    page = 1
    out: list[dict[str, object]] = []
    while True:
        payload = _gh_api_json(
            repo_slug,
            f"milestones?state=all&per_page=100&page={page}",
        )
        if not isinstance(payload, list):
            raise CliError("unexpected GitHub milestones API response shape")
        if not payload:
            break
        for item in payload:
            if isinstance(item, dict):
                out.append(item)
        page += 1
    return out


def _extract_roadmap_milestones(roadmap_path: Path) -> tuple[list[str], list[str]]:
    if not roadmap_path.exists():
        raise CliError(f"ROADMAP file not found: {roadmap_path}")

    ids: set[str] = set()
    suffix_notes: list[str] = []
    for line in roadmap_path.read_text(encoding="utf-8").splitlines():
        match = ROADMAP_HEADING_RE.match(line)
        if not match:
            continue
        number = int(match.group("number"))
        suffix = match.group("suffix")
        ids.add(f"M{number}")
        if suffix:
            suffix_notes.append(f"Milestone {number}{suffix} mapped to M{number}")

    ordered = sorted(ids, key=lambda title: int(title[1:]))
    dedup_notes = sorted(set(suffix_notes))
    return ordered, dedup_notes


def _merge_desired(roadmap_ids: Iterable[str], explicit: Iterable[str]) -> list[str]:
    merged = set(roadmap_ids)
    for title in explicit:
        candidate = title.strip()
        if candidate:
            merged.add(candidate)
    merged.update(BUCKET_MILESTONES)

    def _sort_key(title: str) -> tuple[int, int | str]:
        if re.fullmatch(r"M\d+", title):
            return (0, int(title[1:]))
        return (1, title)

    return sorted(merged, key=_sort_key)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create missing GitHub milestones from ROADMAP milestone IDs.")
    parser.add_argument("--repo", help="GitHub repo slug owner/name. Defaults to origin remote.")
    parser.add_argument("--roadmap", default="docs/ROADMAP.md", help="Roadmap path to parse milestone headings from.")
    parser.add_argument("--milestone", action="append", default=[], help="Additional milestone title(s) to ensure.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without creating milestones.")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Check milestone presence only; exit non-zero if any desired milestone is missing.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        repo_slug = _resolve_repo_slug(args.repo)
        roadmap_ids, suffix_notes = _extract_roadmap_milestones(Path(args.roadmap))
        desired = _merge_desired(roadmap_ids, args.milestone)
        existing_items = _list_milestones(repo_slug)
    except CliError as exc:
        print(f"ERROR: {exc}")
        return 1

    existing_titles = {
        str(item.get("title")).strip()
        for item in existing_items
        if isinstance(item.get("title"), str) and str(item.get("title")).strip()
    }

    missing = [title for title in desired if title not in existing_titles]
    existed = [title for title in desired if title in existing_titles]

    print(f"repo={repo_slug}")
    print(f"roadmap_milestones={len(roadmap_ids)} desired_total={len(desired)} existing_total={len(existing_titles)}")
    for note in suffix_notes:
        print(f"note: {note}")

    if args.verify_only:
        print(f"verify_only missing={len(missing)}")
        if missing:
            for title in missing:
                print(f"missing: {title}")
            return 1
        print("All desired milestones exist.")
        return 0

    created: list[str] = []
    if args.dry_run:
        for title in missing:
            print(f"would_create: {title}")
    else:
        for title in missing:
            try:
                _gh_api_json(repo_slug, "milestones", method="POST", payload={"title": title})
                created.append(title)
                print(f"created: {title}")
            except CliError as exc:
                # If a concurrent run already created the milestone, continue idempotently.
                if "HTTP 422" in str(exc) and "already exists" in str(exc):
                    print(f"already_exists_race: {title}")
                    continue
                print(f"ERROR: failed creating milestone '{title}': {exc}")
                return 1

    print("summary:")
    print(f"  existed: {len(existed)}")
    print(f"  missing_before: {len(missing)}")
    print(f"  created: {len(created)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
