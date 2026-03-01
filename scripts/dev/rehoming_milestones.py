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
M0_COMMENT_MARKER = "[governance-m0-triage]"
M0_DESCRIPTION_TEXT = "Only ambiguous items allowed. Add explicit `Milestone <N>` or `M<N>` context in issue body for deterministic rehome."

ROADMAP_MILESTONE_HEADING_RE = re.compile(r"^\s*#{2,6}\s+Milestone\s+(\d+)([A-Za-z]?)\b")
ANY_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")
EXPLICIT_MILESTONE_RE = re.compile(r"\bmilestone(?:\s+moved:)?\s*(?:milestone\s*)?(\d+)\b|\bM(\d+)\b", re.IGNORECASE)
LABEL_MILESTONE_RE = re.compile(r"(?:^|[^A-Za-z0-9])M?(\d+)(?:[^A-Za-z0-9]|$)", re.IGNORECASE)
ISSUE_REF_RE = re.compile(r"#(\d+)")
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


@dataclass(frozen=True)
class IssueRecord:
    number: int
    title: str
    body: str
    labels: tuple[str, ...]
    milestone: str | None


@dataclass(frozen=True)
class RehomeDecision:
    number: int
    current_milestone: str | None
    target_milestone: str
    reason: str
    ambiguous: bool


@dataclass(frozen=True)
class M0DrainDecision:
    number: int
    current_milestone: str | None
    target_milestone: str
    reason: str
    ambiguous: bool
    commented: bool


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
        endpoint = f"{endpoint}&page={page}" if "?" in path else f"{endpoint}?page={page}"
        payload = _gh_api_json(endpoint)
        if not isinstance(payload, list):
            raise RehomeError(f"unexpected paginated response for path: {path}")
        if not payload:
            return out
        out.extend(item for item in payload if isinstance(item, dict))
        page += 1


def _parse_roadmap(path: Path) -> tuple[list[str], list[str], dict[int, str]]:
    if not path.exists():
        raise RehomeError(f"roadmap not found: {path}")

    numbers: set[int] = set()
    suffix_aliases: set[tuple[int, str]] = set()
    issue_mappings: dict[int, str] = {}

    current_milestone_title: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        match = ROADMAP_MILESTONE_HEADING_RE.match(stripped)
        if match:
            number = int(match.group(1))
            suffix = match.group(2)
            title = f"M{number}"
            numbers.add(number)
            current_milestone_title = title
            if suffix:
                suffix_aliases.add((number, suffix.upper()))
        elif ANY_HEADING_RE.match(stripped):
            current_milestone_title = None

        if current_milestone_title is not None:
            for issue_match in ISSUE_REF_RE.finditer(line):
                issue_number = int(issue_match.group(1))
                issue_mappings.setdefault(issue_number, current_milestone_title)

    if not numbers:
        raise RehomeError(f"no roadmap milestone headings found in: {path}")

    roadmap_titles = [f"M{number}" for number in sorted(numbers)]
    alias_notes = [f"M{number}{suffix}->M{number}" for number, suffix in sorted(suffix_aliases)]
    return roadmap_titles, alias_notes, issue_mappings


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
        if not isinstance(number, int) or not isinstance(title, str):
            continue
        body = row.get("body") if isinstance(row.get("body"), str) else ""
        milestone_raw = row.get("milestone")
        labels_raw = row.get("labels")
        labels: set[str] = set()
        if isinstance(labels_raw, list):
            for item in labels_raw:
                if isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        labels.add(name.strip())
        milestone = None
        if isinstance(milestone_raw, dict):
            maybe_title = milestone_raw.get("title")
            if isinstance(maybe_title, str) and maybe_title.strip():
                milestone = maybe_title.strip()
        pulls.append(
            PullRequest(
                number=number,
                title=title.strip(),
                body=body,
                labels=tuple(sorted(labels)),
                milestone=milestone,
            )
        )
    return sorted(pulls, key=lambda item: item.number)


def _list_pr_files(repo_slug: str, pr_number: int) -> list[str]:
    rows = _list_paginated(repo_slug, f"pulls/{pr_number}/files?per_page=100")
    out: list[str] = []
    for row in rows:
        name = row.get("filename")
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return sorted(set(out))


def _list_issues(repo_slug: str) -> list[IssueRecord]:
    rows = _list_paginated(repo_slug, "issues?state=all&sort=created&direction=asc&per_page=100")
    out: list[IssueRecord] = []
    for row in rows:
        if isinstance(row.get("pull_request"), dict):
            continue
        number = row.get("number")
        title = row.get("title")
        if not isinstance(number, int) or not isinstance(title, str):
            continue
        body = row.get("body") if isinstance(row.get("body"), str) else ""
        labels_raw = row.get("labels")
        labels: set[str] = set()
        if isinstance(labels_raw, list):
            for item in labels_raw:
                if isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        labels.add(name.strip())
        milestone = None
        milestone_raw = row.get("milestone")
        if isinstance(milestone_raw, dict):
            maybe_title = milestone_raw.get("title")
            if isinstance(maybe_title, str) and maybe_title.strip():
                milestone = maybe_title.strip()
        out.append(
            IssueRecord(
                number=number,
                title=title.strip(),
                body=body,
                labels=tuple(sorted(labels)),
                milestone=milestone,
            )
        )
    return sorted(out, key=lambda item: item.number)


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
            raw = match.group(1)
            if not raw:
                continue
            candidate = f"M{int(raw)}"
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
    numeric = sorted((item for item in roadmap_set if re.fullmatch(r"M\d+", item)), key=lambda item: int(item[1:]))
    if numeric:
        return numeric[0]
    raise RehomeError("no roadmap milestones available for docs fallback")


def _heuristic_target(*, text: str, docs_only: bool, roadmap_set: set[str]) -> tuple[str, str, bool]:
    combined = text.lower()

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

    if "M30" in roadmap_set and _contains_any(combined, ("resume", "cv ingestion", "resume ingestion")):
        return "M30", "heuristic:resume", False

    if "M29" in roadmap_set and _contains_any(combined, ("candidate", "profile", "/v1/profile")):
        return "M29", "heuristic:candidate-profile", False

    if "M34" in roadmap_set and _contains_any(combined, ("dashboard", "ui v0", "frontend", "read-only ui", "timeline")):
        return "M34", "heuristic:ui-dashboard", False

    if "M26" in roadmap_set and _contains_any(
        combined,
        ("provider", "providers", "provider scaffold", "provider execution", "onboarding factory", "robots", "tos"),
    ):
        return "M26", "heuristic:providers", False

    if "M19" in roadmap_set and _contains_any(
        combined,
        ("disaster recovery", "dr drill", "dr validate", "failover", "failback", "restore rehearsal", "ops/onprem"),
    ):
        return "M19", "heuristic:dr", False

    if docs_only:
        return _choose_doc_default(roadmap_set), "heuristic:docs-only", False

    return TRIAGE_MILESTONE_TITLE, "heuristic:ambiguous->triage", True


def _decide_pr_target(
    *,
    pr: PullRequest,
    roadmap_set: set[str],
    get_files: Callable[[int], list[str]],
) -> RehomeDecision:
    text = f"{pr.title}\n{pr.body}"
    explicit = _extract_explicit_milestone(text, roadmap_set)
    if explicit:
        return RehomeDecision(pr.number, pr.milestone, explicit, "explicit-text", False)

    from_labels = _extract_label_milestone(pr.labels, roadmap_set)
    if from_labels:
        return RehomeDecision(pr.number, pr.milestone, from_labels, "labels", False)

    if pr.milestone and pr.milestone in roadmap_set:
        return RehomeDecision(pr.number, pr.milestone, pr.milestone, "keep-existing-roadmap", False)

    files = get_files(pr.number)
    docs_only = _docs_only(files)
    file_text = " ".join(path.lower() for path in files)
    target, reason, ambiguous = _heuristic_target(
        text=f"{text}\n{' '.join(pr.labels)}\n{file_text}", docs_only=docs_only, roadmap_set=roadmap_set
    )
    return RehomeDecision(pr.number, pr.milestone, target, reason, ambiguous)


def _decide_issue_target(
    *,
    issue: IssueRecord,
    roadmap_set: set[str],
    roadmap_issue_map: dict[int, str],
) -> RehomeDecision:
    text = f"{issue.title}\n{issue.body}"
    explicit = _extract_explicit_milestone(text, roadmap_set)
    if explicit:
        return RehomeDecision(issue.number, issue.milestone, explicit, "explicit-text", False)

    mapped = roadmap_issue_map.get(issue.number)
    if mapped and mapped in roadmap_set:
        return RehomeDecision(issue.number, issue.milestone, mapped, "roadmap-explicit-issue-link", False)

    from_labels = _extract_label_milestone(issue.labels, roadmap_set)
    if from_labels:
        return RehomeDecision(issue.number, issue.milestone, from_labels, "labels", False)

    if issue.milestone and issue.milestone in roadmap_set:
        return RehomeDecision(issue.number, issue.milestone, issue.milestone, "keep-existing-roadmap", False)

    docs_only = ("area:docs" in issue.labels) or ("type:docs" in issue.labels)
    target, reason, ambiguous = _heuristic_target(
        text=f"{text}\n{' '.join(issue.labels)}",
        docs_only=docs_only,
        roadmap_set=roadmap_set,
    )
    return RehomeDecision(issue.number, issue.milestone, target, reason, ambiguous)


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


def _set_item_milestone(
    *,
    repo_slug: str,
    item_number: int,
    milestone_title: str,
    milestones_by_title: dict[str, dict[str, object]],
    dry_run: bool,
    item_kind: str,
) -> None:
    row = milestones_by_title.get(milestone_title)
    if not isinstance(row, dict):
        raise RehomeError(f"missing milestone metadata for {milestone_title}")
    number = row.get("number")
    if not isinstance(number, int):
        raise RehomeError(f"invalid milestone number for {milestone_title}")
    if dry_run:
        print(f"DRY-RUN set-milestone {item_kind}=#{item_number} -> {milestone_title}")
        return
    _gh_api_json(
        f"repos/{repo_slug}/issues/{item_number}",
        method="PATCH",
        payload={"milestone": number},
    )
    print(f"updated-milestone {item_kind}=#{item_number} -> {milestone_title}")


def _set_milestone_description(
    *,
    repo_slug: str,
    milestone_title: str,
    milestones_by_title: dict[str, dict[str, object]],
    dry_run: bool,
) -> None:
    row = milestones_by_title.get(milestone_title)
    if not isinstance(row, dict):
        raise RehomeError(f"missing milestone metadata for {milestone_title}")
    number = row.get("number")
    current_description = row.get("description")
    if not isinstance(number, int):
        raise RehomeError(f"invalid milestone number for {milestone_title}")
    if isinstance(current_description, str) and current_description.strip() == M0_DESCRIPTION_TEXT:
        return
    if dry_run:
        print(f"DRY-RUN set-milestone-description milestone={milestone_title}")
        return
    patched = _gh_api_json(
        f"repos/{repo_slug}/milestones/{number}",
        method="PATCH",
        payload={"description": M0_DESCRIPTION_TEXT},
    )
    if isinstance(patched, dict):
        milestones_by_title[milestone_title] = patched
    print(f"updated-milestone-description milestone={milestone_title}")


def _list_open_issues_for_milestone(repo_slug: str, milestone_number: int) -> list[IssueRecord]:
    rows = _list_paginated(repo_slug, f"issues?state=open&milestone={milestone_number}&per_page=100")
    out: list[IssueRecord] = []
    for row in rows:
        if isinstance(row.get("pull_request"), dict):
            continue
        number = row.get("number")
        title = row.get("title")
        if not isinstance(number, int) or not isinstance(title, str):
            continue
        body = row.get("body") if isinstance(row.get("body"), str) else ""
        labels_raw = row.get("labels")
        labels: set[str] = set()
        if isinstance(labels_raw, list):
            for item in labels_raw:
                if isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        labels.add(name.strip())
        out.append(
            IssueRecord(
                number=number,
                title=title.strip(),
                body=body,
                labels=tuple(sorted(labels)),
                milestone=TRIAGE_MILESTONE_TITLE,
            )
        )
    return sorted(out, key=lambda item: item.number)


def _issue_has_m0_comment(repo_slug: str, issue_number: int) -> bool:
    rows = _list_paginated(repo_slug, f"issues/{issue_number}/comments?per_page=100")
    for row in rows:
        body = row.get("body")
        if isinstance(body, str) and M0_COMMENT_MARKER in body:
            return True
    return False


def _add_m0_ambiguity_comment(repo_slug: str, issue_number: int, reason: str, *, dry_run: bool) -> bool:
    if _issue_has_m0_comment(repo_slug, issue_number):
        return False
    body = (
        f"{M0_COMMENT_MARKER} Unable to deterministically map this issue to a roadmap milestone.\n\n"
        f"- reason: `{reason}`\n"
        "- kept in: `M0 - Triage`\n"
        "- required to rehome: add explicit `Milestone <N>` or `M<N>` reference in issue title/body "
        "or link this issue from the matching milestone block in `docs/ROADMAP.md`."
    )
    if dry_run:
        print(f"DRY-RUN add-m0-comment issue=#{issue_number}")
        return True
    _gh_api_json(
        f"repos/{repo_slug}/issues/{issue_number}/comments",
        method="POST",
        payload={"body": body},
    )
    print(f"added-m0-comment issue=#{issue_number}")
    return True


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


def _verify_decisions(
    *,
    decisions: Sequence[RehomeDecision],
    roadmap_set: set[str],
) -> tuple[list[int], list[int], list[int]]:
    missing: list[int] = []
    catch_all: list[int] = []
    non_roadmap: list[int] = []
    for decision in decisions:
        target = decision.target_milestone
        if target is None:
            missing.append(decision.number)
            continue
        if target in CATCH_ALL_MILESTONES:
            catch_all.append(decision.number)
            continue
        if target not in roadmap_set and target != TRIAGE_MILESTONE_TITLE:
            non_roadmap.append(decision.number)
    return missing, catch_all, non_roadmap


def _print_summary(
    *,
    mode: str,
    entity: str,
    roadmap_milestones: Sequence[str],
    alias_notes: Sequence[str],
    decisions: Sequence[RehomeDecision],
) -> None:
    moved_from_catchall = Counter()
    assigned_by_target = Counter()
    ambiguous_numbers: list[int] = []
    for decision in decisions:
        if (
            decision.current_milestone in CATCH_ALL_MILESTONES
            and decision.current_milestone != decision.target_milestone
        ):
            moved_from_catchall[decision.current_milestone] += 1
        if decision.current_milestone != decision.target_milestone:
            assigned_by_target[decision.target_milestone] += 1
        if decision.ambiguous:
            ambiguous_numbers.append(decision.number)

    changed_count = sum(1 for d in decisions if d.current_milestone != d.target_milestone)
    print("MILESTONE_REHOME_SUMMARY")
    print(f"mode: {mode}")
    print(f"entity: {entity}")
    print(f"roadmap_milestones: {', '.join(roadmap_milestones)}")
    print(f"roadmap_alias_mapping: {', '.join(alias_notes) if alias_notes else '(none)'}")
    print(f"total_{entity}: {len(decisions)}")
    print(f"changed_{entity}: {changed_count}")
    print("moved_from_catchall:")
    for title in CATCH_ALL_MILESTONES:
        print(f"  {title}: {moved_from_catchall.get(title, 0)}")
    print("assigned_by_target:")
    for title in sorted(assigned_by_target, key=lambda item: (item != TRIAGE_MILESTONE_TITLE, item)):
        print(f"  {title}: {assigned_by_target[title]}")
    print(
        f"ambiguous_triage_{entity}: "
        f"{', '.join(str(number) for number in sorted(ambiguous_numbers)) if ambiguous_numbers else '(none)'}"
    )


def _write_report(
    path: Path,
    *,
    mode: str,
    entity: str,
    repo_slug: str,
    roadmap_milestones: Sequence[str],
    alias_notes: Sequence[str],
    decisions: Sequence[RehomeDecision],
) -> None:
    changed = [d for d in decisions if d.current_milestone != d.target_milestone]
    ambiguous = sorted(d.number for d in decisions if d.ambiguous)
    counts = Counter(d.target_milestone for d in changed)
    lines: list[str] = []
    lines.append("# Milestone Rehome Report")
    lines.append("")
    lines.append(f"- repo: `{repo_slug}`")
    lines.append(f"- mode: `{mode}`")
    lines.append(f"- entity: `{entity}`")
    lines.append(f"- total scanned: `{len(decisions)}`")
    lines.append(f"- changed: `{len(changed)}`")
    lines.append("")
    lines.append("## Roadmap")
    lines.append(f"- milestones: `{', '.join(roadmap_milestones)}`")
    lines.append(f"- alias mapping: `{', '.join(alias_notes) if alias_notes else '(none)'}`")
    lines.append("")
    lines.append("## Assigned Counts")
    if counts:
        for key in sorted(counts, key=lambda item: (item != TRIAGE_MILESTONE_TITLE, item)):
            lines.append(f"- `{key}`: `{counts[key]}`")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Ambiguous")
    if ambiguous:
        lines.append(f"- `{', '.join(str(n) for n in ambiguous)}`")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Changes")
    if changed:
        for d in sorted(changed, key=lambda item: item.number):
            lines.append(
                f"- `{entity[:-1]} #{d.number}`: `{d.current_milestone or '(none)'}` -> `{d.target_milestone}` ({d.reason})"
            )
    else:
        lines.append("- (none)")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rehome PR/issue milestones from catch-all buckets into roadmap milestones using deterministic rules."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print proposed moves without mutating GitHub.")
    mode.add_argument("--apply", action="store_true", help="Apply milestone rehoming updates.")
    mode.add_argument(
        "--verify", action="store_true", help="Verify no item uses catch-all milestone and all items are assigned."
    )
    parser.add_argument("--rehome-issues", action="store_true", help="Operate on issues instead of pull requests.")
    parser.add_argument(
        "--drain-m0-open",
        action="store_true",
        help="Process open issues in M0 - Triage: rehome deterministically or add ambiguity comments.",
    )
    parser.add_argument(
        "--repo", default=None, help="GitHub repository slug (<owner>/<repo>). Defaults to origin remote."
    )
    parser.add_argument(
        "--roadmap", default=str(DEFAULT_ROADMAP_PATH), help="Roadmap file path (default: docs/ROADMAP.md)."
    )
    parser.add_argument("--max-prs", type=int, default=0, help="Optional limit for PR inventory size (0 = all).")
    parser.add_argument("--max-issues", type=int, default=0, help="Optional limit for issue inventory size (0 = all).")
    parser.add_argument("--report", default=None, help="Optional markdown report output path.")
    return parser.parse_args(argv)


def _refresh_pr_decisions(
    repo_slug: str,
    *,
    roadmap_set: set[str],
    get_files: Callable[[int], list[str]],
) -> list[RehomeDecision]:
    return [
        _decide_pr_target(pr=pr, roadmap_set=roadmap_set, get_files=get_files) for pr in _list_pull_requests(repo_slug)
    ]


def _refresh_issue_decisions(
    repo_slug: str,
    *,
    roadmap_set: set[str],
    roadmap_issue_map: dict[int, str],
) -> list[RehomeDecision]:
    return [
        _decide_issue_target(issue=issue, roadmap_set=roadmap_set, roadmap_issue_map=roadmap_issue_map)
        for issue in _list_issues(repo_slug)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "dry-run"
    if args.apply:
        mode = "apply"
    elif args.verify:
        mode = "verify"

    try:
        repo_slug = _resolve_repo_slug(args.repo)
        roadmap_milestones, alias_notes, roadmap_issue_map = _parse_roadmap(Path(args.roadmap))
        roadmap_set = set(roadmap_milestones)
        milestones_by_title = _list_repo_milestones(repo_slug)
        report_path = Path(args.report) if args.report else None

        if args.rehome_issues and args.drain_m0_open:
            raise RehomeError("cannot combine --rehome-issues with --drain-m0-open")

        if args.drain_m0_open:
            entity = "issues"
            m0_row = milestones_by_title.get(TRIAGE_MILESTONE_TITLE)
            if not isinstance(m0_row, dict):
                raise RehomeError(f"{TRIAGE_MILESTONE_TITLE} milestone not found")
            m0_number = m0_row.get("number")
            if not isinstance(m0_number, int):
                raise RehomeError(f"invalid milestone number for {TRIAGE_MILESTONE_TITLE}")

            open_issues = _list_open_issues_for_milestone(repo_slug, m0_number)
            decisions: list[M0DrainDecision] = []
            for issue in open_issues:
                proposal = _decide_issue_target(
                    issue=issue, roadmap_set=roadmap_set, roadmap_issue_map=roadmap_issue_map
                )
                target = proposal.target_milestone
                ambiguous = proposal.ambiguous or target == TRIAGE_MILESTONE_TITLE
                commented = False
                decisions.append(
                    M0DrainDecision(
                        number=issue.number,
                        current_milestone=issue.milestone,
                        target_milestone=target,
                        reason=proposal.reason,
                        ambiguous=ambiguous,
                        commented=commented,
                    )
                )

            print("M0_DRAIN_SUMMARY")
            print(f"mode: {mode}")
            print(f"repo: {repo_slug}")
            print(f"open_m0_issues: {len(decisions)}")
            print(f"rehome_candidates: {sum(1 for d in decisions if d.target_milestone != TRIAGE_MILESTONE_TITLE)}")
            print(f"ambiguous_candidates: {sum(1 for d in decisions if d.target_milestone == TRIAGE_MILESTONE_TITLE)}")

            if mode == "verify":
                unresolved: list[int] = []
                for d in decisions:
                    if d.target_milestone == TRIAGE_MILESTONE_TITLE and not _issue_has_m0_comment(repo_slug, d.number):
                        unresolved.append(d.number)
                print(f"m0_issues_without_comment: {', '.join(str(n) for n in unresolved) if unresolved else '(none)'}")
                if unresolved:
                    print("M0_DRAIN_VERIFY_FAILED", file=sys.stderr)
                    return 1
                print("M0_DRAIN_VERIFY_OK")
                return 0

            if mode == "dry-run":
                for d in decisions:
                    print(
                        f"proposal issue=#{d.number} current={d.current_milestone or '(none)'} "
                        f"target={d.target_milestone} reason={d.reason}"
                    )
                print("M0_DRAIN_DRY_RUN_OK")
                return 0

            # apply
            _set_milestone_description(
                repo_slug=repo_slug,
                milestone_title=TRIAGE_MILESTONE_TITLE,
                milestones_by_title=milestones_by_title,
                dry_run=False,
            )
            applied_comments = 0
            for d in decisions:
                if d.target_milestone != TRIAGE_MILESTONE_TITLE:
                    _ensure_milestone_exists(
                        repo_slug=repo_slug,
                        milestone_title=d.target_milestone,
                        milestones_by_title=milestones_by_title,
                        dry_run=False,
                    )
                    _set_item_milestone(
                        repo_slug=repo_slug,
                        item_number=d.number,
                        milestone_title=d.target_milestone,
                        milestones_by_title=milestones_by_title,
                        dry_run=False,
                        item_kind="issue",
                    )
                else:
                    if _add_m0_ambiguity_comment(repo_slug, d.number, d.reason, dry_run=False):
                        applied_comments += 1

            remaining_open = _list_open_issues_for_milestone(repo_slug, m0_number)
            print(f"remaining_open_m0_issues: {len(remaining_open)}")
            print(f"new_ambiguity_comments: {applied_comments}")
            print("M0_DRAIN_APPLY_OK")
            return 0

        if args.rehome_issues:
            entity = "issues"
            issues = _list_issues(repo_slug)
            if args.max_issues > 0:
                issues = issues[: args.max_issues]
            decisions = [
                _decide_issue_target(issue=item, roadmap_set=roadmap_set, roadmap_issue_map=roadmap_issue_map)
                for item in issues
            ]

            if mode == "verify":
                missing, catch_all, non_roadmap = _verify_decisions(decisions=decisions, roadmap_set=roadmap_set)
                print("MILESTONE_REHOME_VERIFY")
                print(f"repo: {repo_slug}")
                print("entity: issues")
                print(f"total_issues: {len(decisions)}")
                print(f"missing_milestone_count: {len(missing)}")
                print(f"catchall_milestone_count: {len(catch_all)}")
                print(f"nonroadmap_milestone_count: {len(non_roadmap)}")
                if missing:
                    print(f"missing_milestone_issues: {', '.join(str(item) for item in missing)}")
                if catch_all:
                    print(f"catchall_milestone_issues: {', '.join(str(item) for item in catch_all)}")
                if non_roadmap:
                    print(f"nonroadmap_milestone_issues: {', '.join(str(item) for item in non_roadmap)}")
                if report_path is not None:
                    _write_report(
                        report_path,
                        mode=mode,
                        entity=entity,
                        repo_slug=repo_slug,
                        roadmap_milestones=roadmap_milestones,
                        alias_notes=alias_notes,
                        decisions=decisions,
                    )
                    print(f"report: {report_path}")
                if missing or catch_all:
                    print("MILESTONE_REHOME_VERIFY_FAILED", file=sys.stderr)
                    return 1
                print("MILESTONE_REHOME_VERIFY_OK")
                return 0

            _print_summary(
                mode=mode,
                entity=entity,
                roadmap_milestones=roadmap_milestones,
                alias_notes=alias_notes,
                decisions=decisions,
            )
            for decision in decisions:
                if decision.current_milestone != decision.target_milestone:
                    print(
                        f"proposal issue=#{decision.number} current={decision.current_milestone or '(none)'} "
                        f"target={decision.target_milestone} reason={decision.reason}"
                    )

            if mode == "dry-run":
                if report_path is not None:
                    _write_report(
                        report_path,
                        mode=mode,
                        entity=entity,
                        repo_slug=repo_slug,
                        roadmap_milestones=roadmap_milestones,
                        alias_notes=alias_notes,
                        decisions=decisions,
                    )
                    print(f"report: {report_path}")
                print("MILESTONE_REHOME_DRY_RUN_OK")
                return 0

            for decision in decisions:
                if decision.current_milestone == decision.target_milestone:
                    continue
                _ensure_milestone_exists(
                    repo_slug=repo_slug,
                    milestone_title=decision.target_milestone,
                    milestones_by_title=milestones_by_title,
                    dry_run=False,
                )
                _set_item_milestone(
                    repo_slug=repo_slug,
                    item_number=decision.number,
                    milestone_title=decision.target_milestone,
                    milestones_by_title=milestones_by_title,
                    dry_run=False,
                    item_kind="issue",
                )

            refreshed = _refresh_issue_decisions(
                repo_slug,
                roadmap_set=roadmap_set,
                roadmap_issue_map=roadmap_issue_map,
            )
            missing, catch_all, non_roadmap = _verify_decisions(decisions=refreshed, roadmap_set=roadmap_set)
            if report_path is not None:
                _write_report(
                    report_path,
                    mode=mode,
                    entity=entity,
                    repo_slug=repo_slug,
                    roadmap_milestones=roadmap_milestones,
                    alias_notes=alias_notes,
                    decisions=refreshed,
                )
                print(f"report: {report_path}")
            if missing or catch_all:
                print(
                    f"post-apply-verify-failed missing={len(missing)} catchall={len(catch_all)} nonroadmap={len(non_roadmap)}",
                    file=sys.stderr,
                )
                return 1
            print("MILESTONE_REHOME_APPLY_OK")
            return 0

        # Default: PR rehoming mode.
        entity = "prs"
        pulls = _list_pull_requests(repo_slug)
        if args.max_prs > 0:
            pulls = pulls[: args.max_prs]

        files_cache: dict[int, list[str]] = {}

        def _get_files(pr_number: int) -> list[str]:
            cached = files_cache.get(pr_number)
            if cached is not None:
                return cached
            value = _list_pr_files(repo_slug, pr_number)
            files_cache[pr_number] = value
            return value

        decisions = [_decide_pr_target(pr=item, roadmap_set=roadmap_set, get_files=_get_files) for item in pulls]

        if mode == "verify":
            missing, catch_all, non_roadmap = _verify_decisions(decisions=decisions, roadmap_set=roadmap_set)
            print("MILESTONE_REHOME_VERIFY")
            print(f"repo: {repo_slug}")
            print("entity: prs")
            print(f"total_prs: {len(decisions)}")
            print(f"missing_milestone_count: {len(missing)}")
            print(f"catchall_milestone_count: {len(catch_all)}")
            print(f"nonroadmap_milestone_count: {len(non_roadmap)}")
            if missing:
                print(f"missing_milestone_prs: {', '.join(str(item) for item in missing)}")
            if catch_all:
                print(f"catchall_milestone_prs: {', '.join(str(item) for item in catch_all)}")
            if non_roadmap:
                print(f"nonroadmap_milestone_prs: {', '.join(str(item) for item in non_roadmap)}")
            if report_path is not None:
                _write_report(
                    report_path,
                    mode=mode,
                    entity=entity,
                    repo_slug=repo_slug,
                    roadmap_milestones=roadmap_milestones,
                    alias_notes=alias_notes,
                    decisions=decisions,
                )
                print(f"report: {report_path}")
            if missing or catch_all:
                print("MILESTONE_REHOME_VERIFY_FAILED", file=sys.stderr)
                return 1
            print("MILESTONE_REHOME_VERIFY_OK")
            return 0

        _print_summary(
            mode=mode,
            entity=entity,
            roadmap_milestones=roadmap_milestones,
            alias_notes=alias_notes,
            decisions=decisions,
        )
        for decision in decisions:
            if decision.current_milestone != decision.target_milestone:
                print(
                    f"proposal pr=#{decision.number} current={decision.current_milestone or '(none)'} "
                    f"target={decision.target_milestone} reason={decision.reason}"
                )

        if mode == "dry-run":
            if report_path is not None:
                _write_report(
                    report_path,
                    mode=mode,
                    entity=entity,
                    repo_slug=repo_slug,
                    roadmap_milestones=roadmap_milestones,
                    alias_notes=alias_notes,
                    decisions=decisions,
                )
                print(f"report: {report_path}")
            print("MILESTONE_REHOME_DRY_RUN_OK")
            return 0

        for decision in decisions:
            if decision.current_milestone == decision.target_milestone:
                continue
            _ensure_milestone_exists(
                repo_slug=repo_slug,
                milestone_title=decision.target_milestone,
                milestones_by_title=milestones_by_title,
                dry_run=False,
            )
            _set_item_milestone(
                repo_slug=repo_slug,
                item_number=decision.number,
                milestone_title=decision.target_milestone,
                milestones_by_title=milestones_by_title,
                dry_run=False,
                item_kind="pr",
            )

        refreshed = _refresh_pr_decisions(repo_slug, roadmap_set=roadmap_set, get_files=_get_files)
        missing, catch_all, non_roadmap = _verify_decisions(decisions=refreshed, roadmap_set=roadmap_set)
        if missing or catch_all:
            print(
                f"post-apply-verify-failed missing={len(missing)} catchall={len(catch_all)} nonroadmap={len(non_roadmap)}",
                file=sys.stderr,
            )
            return 1

        _delete_or_archive_catch_alls(
            repo_slug=repo_slug,
            milestones_by_title=milestones_by_title,
            dry_run=False,
        )
        if report_path is not None:
            _write_report(
                report_path,
                mode=mode,
                entity=entity,
                repo_slug=repo_slug,
                roadmap_milestones=roadmap_milestones,
                alias_notes=alias_notes,
                decisions=refreshed,
            )
            print(f"report: {report_path}")
        print("MILESTONE_REHOME_APPLY_OK")
        return 0
    except RehomeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
