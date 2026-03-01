#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROADMAP_PATH = Path("docs/ROADMAP.md")
TRIAGE_MILESTONE_TITLE = "M0 - Triage"
ROADMAP_HEADING_RE = re.compile(r"^\s*#{2,6}\s+Milestone\s+(\d+)([A-Za-z]?)\b")


class MilestoneCleanupError(RuntimeError):
    """Raised when milestone cleanup cannot continue safely."""


@dataclass(frozen=True)
class MilestoneCounts:
    open_issues: int
    open_prs: int
    closed_issues: int
    closed_prs: int

    @property
    def total_items(self) -> int:
        return self.open_issues + self.open_prs + self.closed_issues + self.closed_prs


@dataclass(frozen=True)
class MilestoneDecision:
    title: str
    number: int
    action: str
    reason: str
    counts: MilestoneCounts


def _run(cmd: list[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, input=input_text)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "(no stderr)"
        raise MilestoneCleanupError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    return proc.stdout


def _resolve_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo.strip()
    remote_url = _run(["git", "config", "--get", "remote.origin.url"]).strip()
    if not remote_url:
        raise MilestoneCleanupError("could not resolve repository from git remote.origin.url")
    https_match = re.match(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    ssh_match = re.match(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    match = https_match or ssh_match
    if not match:
        raise MilestoneCleanupError(f"unsupported GitHub remote URL format: {remote_url}")
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
            raise MilestoneCleanupError(f"unexpected paginated response for {path}")
        if not payload:
            return out
        out.extend(item for item in payload if isinstance(item, dict))
        page += 1


def _parse_roadmap_milestones(path: Path) -> tuple[set[str], set[str]]:
    if not path.exists():
        raise MilestoneCleanupError(f"roadmap not found: {path}")
    roadmap_titles: set[str] = set()
    completed_titles: set[str] = set()
    current_title: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        match = ROADMAP_HEADING_RE.match(stripped)
        if match:
            number = int(match.group(1))
            title = f"M{number}"
            roadmap_titles.add(title)
            current_title = title
            if "✅" in stripped:
                completed_titles.add(title)
            continue
        if current_title is not None and stripped.startswith("Status:") and "✅" in stripped:
            completed_titles.add(current_title)
    if not roadmap_titles:
        raise MilestoneCleanupError("no roadmap milestone headings found")
    return roadmap_titles, completed_titles


def _list_repo_milestones(repo_slug: str) -> list[dict[str, object]]:
    return _list_paginated(f"repos/{repo_slug}/milestones?state=all&per_page=100")


def _milestone_item_counts(repo_slug: str, milestone_number: int) -> MilestoneCounts:
    rows = _list_paginated(f"repos/{repo_slug}/issues?state=all&milestone={milestone_number}&per_page=100")
    open_issues = 0
    open_prs = 0
    closed_issues = 0
    closed_prs = 0
    for row in rows:
        is_pr = isinstance(row.get("pull_request"), dict)
        state = row.get("state")
        if state == "open":
            if is_pr:
                open_prs += 1
            else:
                open_issues += 1
        else:
            if is_pr:
                closed_prs += 1
            else:
                closed_issues += 1
    return MilestoneCounts(
        open_issues=open_issues,
        open_prs=open_prs,
        closed_issues=closed_issues,
        closed_prs=closed_prs,
    )


def _patch_milestone(repo_slug: str, number: int, *, title: str | None = None, state: str | None = None) -> None:
    payload: dict[str, object] = {}
    if title is not None:
        payload["title"] = title
    if state is not None:
        payload["state"] = state
    _gh_api_json(f"repos/{repo_slug}/milestones/{number}", method="PATCH", payload=payload)


def _delete_milestone(repo_slug: str, number: int) -> None:
    _gh_api_json(f"repos/{repo_slug}/milestones/{number}", method="DELETE")


def _write_report(path: Path, *, repo_slug: str, mode: str, decisions: list[MilestoneDecision]) -> None:
    lines: list[str] = []
    lines.append("# Milestone Cleanup Report")
    lines.append("")
    lines.append(f"- repo: `{repo_slug}`")
    lines.append(f"- mode: `{mode}`")
    lines.append(f"- milestones evaluated: `{len(decisions)}`")
    lines.append("")
    lines.append("## Decisions")
    if not decisions:
        lines.append("- (none)")
    for d in decisions:
        counts = d.counts
        lines.append(
            f"- `{d.title}` action=`{d.action}` reason=`{d.reason}` "
            f"(open_issues={counts.open_issues}, open_prs={counts.open_prs}, "
            f"closed_issues={counts.closed_issues}, closed_prs={counts.closed_prs})"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup/normalize GitHub milestones against roadmap truth.")
    parser.add_argument("--repo", default=None, help="GitHub repository slug (<owner>/<repo>).")
    parser.add_argument("--roadmap", default=str(DEFAULT_ROADMAP_PATH), help="Roadmap path.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument("--report", default=None, help="Optional markdown report output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "apply" if args.apply else "dry-run"
    report_path = Path(args.report) if args.report else None
    try:
        repo_slug = _resolve_repo_slug(args.repo)
        roadmap_titles, completed_titles = _parse_roadmap_milestones(Path(args.roadmap))
        rows = _list_repo_milestones(repo_slug)

        decisions: list[MilestoneDecision] = []
        for row in rows:
            title = row.get("title")
            number = row.get("number")
            state = row.get("state")
            if not isinstance(title, str) or not title.strip() or not isinstance(number, int):
                continue
            clean_title = title.strip()
            clean_state = state if isinstance(state, str) else "open"
            counts = _milestone_item_counts(repo_slug, number)
            is_roadmap = clean_title in roadmap_titles or clean_title == TRIAGE_MILESTONE_TITLE

            action = "keep"
            reason = "roadmap-active"
            if not is_roadmap:
                if counts.total_items == 0:
                    action = "delete"
                    reason = "non-roadmap-empty"
                    if args.apply:
                        _delete_milestone(repo_slug, number)
                else:
                    archived_title = (
                        clean_title if clean_title.startswith("ARCHIVED - ") else f"ARCHIVED - {clean_title}"
                    )
                    action = "archive-close"
                    reason = "non-roadmap-has-history"
                    if args.apply:
                        _patch_milestone(repo_slug, number, title=archived_title, state="closed")
            else:
                if clean_title in completed_titles and (counts.open_issues + counts.open_prs == 0):
                    action = "close"
                    reason = "roadmap-complete-no-open-items"
                    if args.apply and clean_state != "closed":
                        _patch_milestone(repo_slug, number, state="closed")
                else:
                    action = "open"
                    reason = "roadmap-active-or-open-items"
                    if args.apply and clean_state == "closed":
                        _patch_milestone(repo_slug, number, state="open")

            decisions.append(
                MilestoneDecision(
                    title=clean_title,
                    number=number,
                    action=action,
                    reason=reason,
                    counts=counts,
                )
            )

        print("MILESTONE_CLEANUP_SUMMARY")
        print(f"mode: {mode}")
        print(f"repo: {repo_slug}")
        print(f"evaluated: {len(decisions)}")
        print(f"delete_count: {sum(1 for d in decisions if d.action == 'delete')}")
        print(f"archive_count: {sum(1 for d in decisions if d.action == 'archive-close')}")
        print(f"close_count: {sum(1 for d in decisions if d.action == 'close')}")
        print(f"open_count: {sum(1 for d in decisions if d.action == 'open')}")
        for d in sorted(decisions, key=lambda item: item.number):
            c = d.counts
            print(
                f"milestone={d.title} action={d.action} reason={d.reason} "
                f"open_issues={c.open_issues} open_prs={c.open_prs} "
                f"closed_issues={c.closed_issues} closed_prs={c.closed_prs}"
            )

        if report_path is not None:
            _write_report(report_path, repo_slug=repo_slug, mode=mode, decisions=decisions)
            print(f"report: {report_path}")
        print("MILESTONE_CLEANUP_OK")
        return 0
    except MilestoneCleanupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
