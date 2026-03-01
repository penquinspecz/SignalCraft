#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROADMAP_PATH = Path("docs/ROADMAP.md")
CATCH_ALL_MILESTONES = ("Infra & Tooling", "Docs & Governance", "Backlog Cleanup")
TRIAGE_MILESTONE_TITLE = "M0 - Triage"

ROADMAP_MILESTONE_HEADING_RE = re.compile(r"^\s*#{2,6}\s+Milestone\s+(\d+)([A-Za-z]?)\b")
EXPLICIT_MILESTONE_RE = re.compile(r"\bmilestone(?:\s+moved:)?\s*(?:milestone\s*)?(\d+)\b|\bM(\d+)\b", re.IGNORECASE)
LABEL_MILESTONE_RE = re.compile(r"(?:^|[^A-Za-z0-9])M?(\d+)(?:[^A-Za-z0-9]|$)", re.IGNORECASE)
README_RE = re.compile(r"(^|/)README[^/]*$", re.IGNORECASE)


class RehomeError(RuntimeError):
    """Raised when milestone rehoming cannot proceed safely."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    body: str
    labels: tuple[str, ...]
    milestone: str | None
    merged_at: str | None
    state: str


@dataclass(frozen=True)
class RehomeDecision:
    number: int
    current_milestone: str | None
    target_milestone: str
    reason: str
    ambiguous: bool


def _run(cmd: Sequence[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, input=input_text)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "(no stderr)"
        raise RehomeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    return proc.stdout


def _resolve_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo.strip()

    remote_url = _run(["git", "config", "--get", "remote.origin.url"]).strip()
    if not remote_url:
        raise RehomeError("could not resolve repository from git remote.origin.url")

    https_match = re.match(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    ssh_match = re.match(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    match = https_match or ssh_match
    if not match:
        raise RehomeError(f"unsupported GitHub remote URL format: {remote_url}")
    return f"{match.group('owner')}/{match.group('repo')}"


def _gh_api_json(
    endpoint: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> object:
    cmd = ["gh", "api", endpoint]
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


def _list_paginated(repo_slug: str, path: str) -> list[dict[str, object]]:
    page = 1
    out: list[dict[str, object]] = []
    while True:
        endpoint = f"repos/{repo_slug}/{path}"
        if "?" in path:
            endpoint = f"{endpoint}&page={page}"
        else:
            endpoint = f"{endpoint}?page={page}"
        payload = _gh_api_json(endpoint)
        if not isinstance(payload, list):
            raise RehomeError(f"unexpected paginated response for path: {path}")
        if not payload:
            return out
        out.extend(item for item in payload if isinstance(item, dict))
        page += 1


def _parse_roadmap_milestones(path: Path) -> tuple[list[str], list[str]]:
    if not path.exists():
        raise RehomeError(f"roadmap not found: {path}")
    numbers: set[int] = set()
    alias_notes: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROADMAP_MILESTONE_HEADING_RE.match(line.strip())
        if not match:
            continue
        number = int(match.group(1))
        suffix = match.group(2)
        numbers.add(number)
        if suffix:
            alias_notes.add(f"M{number}{suffix.upper()}->M{number}")
    if not numbers:
        raise RehomeError(f"no roadmap milestone headings found in {path}")
    milestones = [f"M{number}" for number in sorted(numbers)]
    return milestones, sorted(alias_notes)


def _list_repo_milestones(repo_slug: str) -> dict[str, dict[str, object]]:
    rows = _list_paginated(repo_slug, "milestones?state=all&per_page=100")
    out: dict[str, dict[str, object]] = {}
    for item in rows:
        title = item.get("title")
        if isinstance(title, str) and title.strip():
            out[title.strip()] = item
    return out


def _create_milestone(repo_slug: str, title: str) -> dict[str, object]:
    payload = _gh_api_json(
        f"repos/{repo_slug}/milestones",
        method="POST",
        payload={"title": title, "state": "open"},
    )
    if not isinstance(payload, dict):
        raise RehomeError(f"unexpected create milestone response for {title}")
    return payload


def _list_pull_requests(repo_slug: str) -> list[PullRequest]:
    rows = _list_paginated(repo_slug, "pulls?state=all&sort=created&direction=asc&per_page=100")
    pulls: list[PullRequest] = []
    for row in rows:
        number = row.get("number")
        title = row.get("title")
        state = row.get("state")
        if not isinstance(number, int) or not isinstance(title, str) or not isinstance(state, str):
            continue
        body = row.get("body")
        labels_raw = row.get("labels")
        milestone_raw = row.get("milestone")
        merged_at = row.get("merged_at")
        labels: list[str] = []
        if isinstance(labels_raw, list):
            for item in labels_raw:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    labels.append(name.strip())
        milestone = None
        if isinstance(milestone_raw, dict):
            maybe_title = milestone_raw.get("title")
            if isinstance(maybe_title, str) and maybe_title.strip():
                milestone = maybe_title.strip()
        pulls.append(
            PullRequest(
                number=number,
                title=title.strip(),
                body=body if isinstance(body, str) else "",
                labels=tuple(sorted(set(labels))),
                milestone=milestone,
                merged_at=merged_at if isinstance(merged_at, str) else None,
                state=state,
            )
        )
    pulls.sort(key=lambda pr: pr.number)
    return pulls


def _list_pr_files(repo_slug: str, pr_number: int) -> list[str]:
    rows = _list_paginated(repo_slug, f"pulls/{pr_number}/files?per_page=100")
    out: list[str] = []
    for row in rows:
        name = row.get("filename")
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return sorted(set(out))


def _extract_explicit_milestone(text: str, roadmap_set: set[str]) -> str | None:
    for match in EXPLICIT_MILESTONE_RE.finditer(text):
        raw = match.group(1) or match.group(2)
        if not raw:
            continue
        candidate = f"M{int(raw)}"
        if candidate in roadmap_set:
            return candidate
    return None


def _extract_label_milestone(labels: Sequence[str], roadmap_set: set[str]) -> str | None:
    for label in sorted(labels):
        lower = label.lower()
        if lower.startswith("milestone:"):
            maybe = lower.split(":", 1)[1].strip()
            if maybe.startswith("m") and maybe[1:].isdigit():
                candidate = f"M{int(maybe[1:])}"
                if candidate in roadmap_set:
                    return candidate
            if maybe.isdigit():
                candidate = f"M{int(maybe)}"
                if candidate in roadmap_set:
                    return candidate
        for match in LABEL_MILESTONE_RE.finditer(label):
            maybe_num = match.group(1)
            if not maybe_num:
                continue
            candidate = f"M{int(maybe_num)}"
            if candidate in roadmap_set:
                return candidate
    return None


def _is_docs_path(path: str) -> bool:
    return path.startswith("docs/") or bool(README_RE.search(path))


def _docs_only(paths: Sequence[str]) -> bool:
    return bool(paths) and all(_is_docs_path(path) for path in paths)


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term in text for term in terms)


def _choose_doc_default(roadmap_set: set[str]) -> str:
    for candidate in ("M24", "M23", "M22", "M34", "M28"):
        if candidate in roadmap_set:
            return candidate
    numeric = sorted((item for item in roadmap_set if re.fullmatch(r"M\d+", item)), key=lambda v: int(v[1:]))
    if numeric:
        return numeric[0]
    raise RehomeError("no roadmap milestones available for docs-only fallback")


def _heuristic_target(
    *,
    pr: PullRequest,
    files: Sequence[str],
    roadmap_set: set[str],
) -> tuple[str, str, bool]:
    text = f"{pr.title}\n{pr.body}\n{' '.join(pr.labels)}".lower()
    file_text = " ".join(path.lower() for path in files)
    combined = f"{text}\n{file_text}"

    if "M22" in roadmap_set and _contains_any(
        combined,
        (
            "ssrf",
            "dns rebinding",
            "network_shield",
            "network shield",
            "path traversal",
            "symlink",
            "tar slip",
            "restore_onprem",
            "security",
            "cve",
        ),
    ):
        return "M22", "heuristic:security", False

    if "M28" in roadmap_set and _contains_any(combined, ("digest", "alerts", "alerting")):
        return "M28", "heuristic:digest-alerts", False

    if _contains_any(combined, ("resume", "cv ingestion", "resume ingestion")) and "M30" in roadmap_set:
        return "M30", "heuristic:resume", False

    if _contains_any(combined, ("candidate", "profile", "/v1/profile")) and "M29" in roadmap_set:
        return "M29", "heuristic:candidate-profile", False

    if "M34" in roadmap_set and _contains_any(combined, ("dashboard", "ui v0", "frontend", "read-only ui", "timeline")):
        return "M34", "heuristic:ui-dashboard", False

    if "M26" in roadmap_set and _contains_any(
        combined,
        (
            "provider",
            "providers",
            "provider scaffold",
            "provider availability",
            "provider execution",
            "onboarding factory",
        ),
    ):
        return "M26", "heuristic:providers", False

    if "M19" in roadmap_set and _contains_any(
        combined,
        (
            "disaster recovery",
            "dr drill",
            "dr validate",
            "failover",
            "failback",
            "restore rehearsal",
            "scripts/ops/",
            "ops/onprem",
        ),
    ):
        return "M19", "heuristic:dr", False

    if _docs_only(files):
        return _choose_doc_default(roadmap_set), "heuristic:docs-only", False

    return TRIAGE_MILESTONE_TITLE, "heuristic:ambiguous->triage", True


def _decide_target(
    *,
    pr: PullRequest,
    roadmap_set: set[str],
    get_files: Callable[[int], list[str]],
) -> RehomeDecision:
    explicit = _extract_explicit_milestone(f"{pr.title}\n{pr.body}", roadmap_set)
    if explicit:
        return RehomeDecision(
            number=pr.number,
            current_milestone=pr.milestone,
            target_milestone=explicit,
            reason="explicit-text",
            ambiguous=False,
        )

    from_labels = _extract_label_milestone(pr.labels, roadmap_set)
    if from_labels:
        return RehomeDecision(
            number=pr.number,
            current_milestone=pr.milestone,
            target_milestone=from_labels,
            reason="labels",
            ambiguous=False,
        )

    if pr.milestone and pr.milestone in roadmap_set:
        return RehomeDecision(
            number=pr.number,
            current_milestone=pr.milestone,
            target_milestone=pr.milestone,
            reason="keep-existing-roadmap",
            ambiguous=False,
        )

    files = get_files(pr.number)
    target, reason, ambiguous = _heuristic_target(pr=pr, files=files, roadmap_set=roadmap_set)
    return RehomeDecision(
        number=pr.number,
        current_milestone=pr.milestone,
        target_milestone=target,
        reason=reason,
        ambiguous=ambiguous,
    )


def _ensure_milestone_exists(
    *,
    repo_slug: str,
    milestone_title: str,
    milestones_by_title: dict[str, dict[str, object]],
    dry_run: bool,
) -> None:
    if milestone_title in milestones_by_title:
        return
    if dry_run:
        print(f"DRY-RUN create-milestone title={milestone_title}")
        milestones_by_title[milestone_title] = {"number": -1, "title": milestone_title}
        return
    created = _create_milestone(repo_slug, milestone_title)
    milestones_by_title[milestone_title] = created
    print(f"created-milestone title={milestone_title}")


def _set_pr_milestone(
    *,
    repo_slug: str,
    pr_number: int,
    milestone_title: str,
    milestones_by_title: dict[str, dict[str, object]],
    dry_run: bool,
) -> None:
    row = milestones_by_title.get(milestone_title)
    if not isinstance(row, dict):
        raise RehomeError(f"missing milestone metadata for {milestone_title}")
    number = row.get("number")
    if not isinstance(number, int):
        raise RehomeError(f"invalid milestone number for {milestone_title}")
    if dry_run:
        print(f"DRY-RUN set-milestone pr=#{pr_number} -> {milestone_title}")
        return
    _gh_api_json(
        f"repos/{repo_slug}/issues/{pr_number}",
        method="PATCH",
        payload={"milestone": number},
    )
    print(f"updated-milestone pr=#{pr_number} -> {milestone_title}")


def _count_prs_in_milestone(repo_slug: str, milestone_number: int) -> int:
    rows = _list_paginated(repo_slug, f"issues?state=all&milestone={milestone_number}&per_page=100")
    return sum(1 for row in rows if isinstance(row.get("pull_request"), dict))


def _delete_or_archive_catch_alls(
    *,
    repo_slug: str,
    milestones_by_title: dict[str, dict[str, object]],
    dry_run: bool,
) -> None:
    for title in CATCH_ALL_MILESTONES:
        row = milestones_by_title.get(title)
        if not isinstance(row, dict):
            print(f"catch-all-milestone-missing: {title}")
            continue
        number = row.get("number")
        if not isinstance(number, int):
            raise RehomeError(f"invalid milestone number for catch-all {title}")
        pr_count = _count_prs_in_milestone(repo_slug, number)
        if pr_count > 0:
            print(f"catch-all-retained-nonempty: {title} prs={pr_count}")
            continue
        if dry_run:
            print(f"DRY-RUN delete-catch-all title={title}")
            continue
        try:
            _gh_api_json(f"repos/{repo_slug}/milestones/{number}", method="DELETE")
            print(f"deleted-catch-all: {title}")
            milestones_by_title.pop(title, None)
            continue
        except RehomeError as exc:
            archived_title = f"ARCHIVED - {title} (empty)"
            print(f"delete-failed-archiving: {title} reason={exc}")
            patched = _gh_api_json(
                f"repos/{repo_slug}/milestones/{number}",
                method="PATCH",
                payload={"title": archived_title, "state": "closed"},
            )
            if isinstance(patched, dict):
                milestones_by_title.pop(title, None)
                milestones_by_title[archived_title] = patched
            print(f"archived-catch-all: {archived_title}")


def _verify_state(
    *,
    pulls: Sequence[PullRequest],
    roadmap_set: set[str],
) -> tuple[list[int], list[int], list[int]]:
    missing: list[int] = []
    catch_all: list[int] = []
    non_roadmap: list[int] = []
    for pr in pulls:
        milestone = pr.milestone
        if milestone is None:
            missing.append(pr.number)
            continue
        if milestone in CATCH_ALL_MILESTONES:
            catch_all.append(pr.number)
            continue
        if milestone not in roadmap_set and milestone != TRIAGE_MILESTONE_TITLE:
            non_roadmap.append(pr.number)
    return missing, catch_all, non_roadmap


def _refresh_pull_milestones(repo_slug: str, pulls: Sequence[PullRequest]) -> list[PullRequest]:
    refreshed: list[PullRequest] = []
    by_number = {pr.number: pr for pr in _list_pull_requests(repo_slug)}
    for pr in pulls:
        latest = by_number.get(pr.number)
        if latest is None:
            refreshed.append(pr)
            continue
        refreshed.append(latest)
    return refreshed


def _print_summary(
    *,
    mode: str,
    roadmap_milestones: Sequence[str],
    alias_notes: Sequence[str],
    decisions: Sequence[RehomeDecision],
    changed_count: int,
) -> None:
    moved_from_catchall = Counter()
    assigned_by_target = Counter()
    ambiguous: list[int] = []
    for decision in decisions:
        if (
            decision.current_milestone in CATCH_ALL_MILESTONES
            and decision.current_milestone != decision.target_milestone
        ):
            moved_from_catchall[decision.current_milestone] += 1
        if decision.current_milestone != decision.target_milestone:
            assigned_by_target[decision.target_milestone] += 1
        if decision.ambiguous:
            ambiguous.append(decision.number)

    print("MILESTONE_REHOME_SUMMARY")
    print(f"mode: {mode}")
    print(f"roadmap_milestones: {', '.join(roadmap_milestones)}")
    print(f"roadmap_alias_mapping: {', '.join(alias_notes) if alias_notes else '(none)'}")
    print(f"total_prs: {len(decisions)}")
    print(f"changed_prs: {changed_count}")
    print("moved_from_catchall:")
    for title in CATCH_ALL_MILESTONES:
        print(f"  {title}: {moved_from_catchall.get(title, 0)}")
    print("assigned_by_target:")
    for title in sorted(assigned_by_target, key=lambda item: (item != TRIAGE_MILESTONE_TITLE, item)):
        print(f"  {title}: {assigned_by_target[title]}")
    print(f"ambiguous_triage_prs: {', '.join(str(number) for number in sorted(ambiguous)) if ambiguous else '(none)'}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rehome PR milestones from catch-all buckets into roadmap milestones using deterministic rules."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="Print proposed PR->milestone moves without mutating GitHub."
    )
    mode.add_argument("--apply", action="store_true", help="Apply milestone rehoming updates.")
    mode.add_argument(
        "--verify", action="store_true", help="Verify no PR uses catch-all milestone and all PRs are assigned."
    )
    parser.add_argument(
        "--repo", default=None, help="GitHub repository slug (<owner>/<repo>). Defaults to origin remote."
    )
    parser.add_argument(
        "--roadmap", default=str(DEFAULT_ROADMAP_PATH), help="Roadmap file path (default: docs/ROADMAP.md)."
    )
    parser.add_argument(
        "--max-prs",
        type=int,
        default=0,
        help="Optional limit for PR inventory size (0 = all). Useful for local smoke testing.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "dry-run"
    if args.apply:
        mode = "apply"
    elif args.verify:
        mode = "verify"

    roadmap_path = Path(args.roadmap)
    repo_slug = _resolve_repo_slug(args.repo)

    try:
        roadmap_milestones, alias_notes = _parse_roadmap_milestones(roadmap_path)
        roadmap_set = set(roadmap_milestones)
        milestones_by_title = _list_repo_milestones(repo_slug)

        pulls = _list_pull_requests(repo_slug)
        if args.max_prs > 0:
            pulls = pulls[: args.max_prs]

        if mode == "verify":
            missing, catch_all, non_roadmap = _verify_state(pulls=pulls, roadmap_set=roadmap_set)
            print("MILESTONE_REHOME_VERIFY")
            print(f"repo: {repo_slug}")
            print(f"total_prs: {len(pulls)}")
            print(f"missing_milestone_count: {len(missing)}")
            print(f"catchall_milestone_count: {len(catch_all)}")
            print(f"nonroadmap_milestone_count: {len(non_roadmap)}")
            if missing:
                print(f"missing_milestone_prs: {', '.join(str(item) for item in missing)}")
            if catch_all:
                print(f"catchall_milestone_prs: {', '.join(str(item) for item in catch_all)}")
            if non_roadmap:
                print(f"nonroadmap_milestone_prs: {', '.join(str(item) for item in non_roadmap)}")
            if missing or catch_all:
                print("MILESTONE_REHOME_VERIFY_FAILED", file=sys.stderr)
                return 1
            print("MILESTONE_REHOME_VERIFY_OK")
            return 0

        files_cache: dict[int, list[str]] = {}

        def _get_files(pr_number: int) -> list[str]:
            cached = files_cache.get(pr_number)
            if cached is not None:
                return cached
            value = _list_pr_files(repo_slug, pr_number)
            files_cache[pr_number] = value
            return value

        decisions = [_decide_target(pr=pr, roadmap_set=roadmap_set, get_files=_get_files) for pr in pulls]
        changes = [item for item in decisions if item.current_milestone != item.target_milestone]

        _print_summary(
            mode=mode,
            roadmap_milestones=roadmap_milestones,
            alias_notes=alias_notes,
            decisions=decisions,
            changed_count=len(changes),
        )

        for decision in changes:
            print(
                f"proposal pr=#{decision.number} current={decision.current_milestone or '(none)'} "
                f"target={decision.target_milestone} reason={decision.reason}"
            )

        if mode == "dry-run":
            print("MILESTONE_REHOME_DRY_RUN_OK")
            return 0

        # Apply mode.
        for decision in changes:
            _ensure_milestone_exists(
                repo_slug=repo_slug,
                milestone_title=decision.target_milestone,
                milestones_by_title=milestones_by_title,
                dry_run=False,
            )
            _set_pr_milestone(
                repo_slug=repo_slug,
                pr_number=decision.number,
                milestone_title=decision.target_milestone,
                milestones_by_title=milestones_by_title,
                dry_run=False,
            )

        refreshed = _refresh_pull_milestones(repo_slug, pulls)
        missing, catch_all, non_roadmap = _verify_state(pulls=refreshed, roadmap_set=roadmap_set)
        if missing or catch_all:
            print(
                "post-apply-verify-failed "
                f"missing={len(missing)} catchall={len(catch_all)} nonroadmap={len(non_roadmap)}",
                file=sys.stderr,
            )
            return 1

        _delete_or_archive_catch_alls(
            repo_slug=repo_slug,
            milestones_by_title=milestones_by_title,
            dry_run=False,
        )
        print("MILESTONE_REHOME_APPLY_OK")
        return 0
    except RehomeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
