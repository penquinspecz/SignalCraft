#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Iterable, Sequence

PROVENANCE_LABELS = ("from-composer", "from-codex", "from-human")
TYPE_LABELS = ("type:feat", "type:fix", "type:chore", "type:docs", "type:refactor", "type:test")
AREA_LABEL_ORDER = (
    "area:engine",
    "area:providers",
    "area:dr",
    "area:release",
    "area:infra",
    "area:docs",
    "area:unknown",
)

REQUIRED_LABEL_SPECS = {
    "from-composer": {"color": "5319E7", "description": "PRs authored/executed via Composer flows"},
    "from-codex": {"color": "1D76DB", "description": "PRs authored/executed directly by Codex"},
    "from-human": {"color": "0E8A16", "description": "PRs authored directly by a human"},
    "type:feat": {"color": "0E8A16", "description": "Feature change"},
    "type:fix": {"color": "D73A4A", "description": "Bug fix"},
    "type:chore": {"color": "BFD4F2", "description": "Maintenance or tooling change"},
    "type:docs": {"color": "0075CA", "description": "Documentation-only or docs-primary change"},
    "type:refactor": {"color": "FBCA04", "description": "Internal refactor with no intended behavior change"},
    "type:test": {"color": "C2E0C6", "description": "Test-only change"},
    "area:engine": {"color": "0E8A16", "description": "Engine/runtime pipeline logic"},
    "area:providers": {"color": "0052CC", "description": "Provider integrations and registry"},
    "area:dr": {"color": "B60205", "description": "Disaster recovery and restore tooling"},
    "area:release": {"color": "5319E7", "description": "Release process and release tooling"},
    "area:infra": {"color": "1D76DB", "description": "Infrastructure and deployment surface"},
    "area:docs": {"color": "0075CA", "description": "Docs-only scope"},
    "area:unknown": {"color": "D4C5F9", "description": "Fallback area when no specific area is inferred"},
}

DOCS_BUCKET = "Docs & Governance"
INFRA_BUCKET = "Infra & Tooling"
BACKLOG_BUCKET = "Backlog Cleanup"
ROADMAP_TITLE_WITH_NAME_RE = re.compile(r"^(M\d+)\s+—\s+.+$")


class CliError(RuntimeError):
    """Raised for recoverable CLI/API failures with stable messages."""


@dataclass(frozen=True)
class MilestoneDecision:
    title: str
    reason: str
    explicit_rule: bool


@dataclass(frozen=True)
class PrResult:
    number: int
    title: str
    labels: list[str]
    milestone: str | None
    ok: bool


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


def _gh_pr_list(repo_slug: str) -> list[dict[str, object]]:
    raw = _run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo_slug,
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,headRefName,labels,milestone,body",
        ]
    )
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise CliError("unexpected gh pr list response shape")
    out: list[dict[str, object]] = []
    for item in payload:
        if isinstance(item, dict):
            out.append(item)
    return out


def _list_paginated(repo_slug: str, path: str) -> list[dict[str, object]]:
    page = 1
    out: list[dict[str, object]] = []
    while True:
        payload = _gh_api_json(repo_slug, f"{path}&page={page}" if "?" in path else f"{path}?page={page}")
        if not isinstance(payload, list):
            raise CliError(f"unexpected paginated response for path: {path}")
        if not payload:
            break
        out.extend(item for item in payload if isinstance(item, dict))
        page += 1
    return out


def _list_repo_labels(repo_slug: str) -> set[str]:
    labels = _list_paginated(repo_slug, "labels?per_page=100")
    out: set[str] = set()
    for label in labels:
        name = label.get("name")
        if isinstance(name, str) and name.strip():
            out.add(name.strip())
    return out


def _list_repo_milestones(repo_slug: str) -> dict[str, int]:
    milestones = _list_paginated(repo_slug, "milestones?state=all&per_page=100")
    out: dict[str, int] = {}
    for item in milestones:
        title = item.get("title")
        number = item.get("number")
        if isinstance(title, str) and title.strip() and isinstance(number, int):
            clean_title = title.strip()
            out[clean_title] = number
            alias_match = ROADMAP_TITLE_WITH_NAME_RE.fullmatch(clean_title)
            if alias_match:
                out.setdefault(alias_match.group(1), number)
    return out


def _list_pr_files(repo_slug: str, pr_number: int) -> list[str]:
    files = _list_paginated(repo_slug, f"pulls/{pr_number}/files?per_page=100")
    out: list[str] = []
    for item in files:
        filename = item.get("filename")
        if isinstance(filename, str):
            out.append(filename)
    return out


def _fetch_pr_issue(repo_slug: str, pr_number: int) -> dict[str, object]:
    payload = _gh_api_json(repo_slug, f"issues/{pr_number}")
    if not isinstance(payload, dict):
        raise CliError(f"unexpected issue response for PR #{pr_number}")
    return payload


def _create_label(repo_slug: str, name: str, color: str, description: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN create-label: {name}")
        return
    try:
        _gh_api_json(
            repo_slug,
            "labels",
            method="POST",
            payload={"name": name, "color": color, "description": description},
        )
        print(f"created-label: {name}")
    except CliError as exc:
        text = str(exc)
        if "HTTP 422" in text:
            print(f"label-exists-race: {name}")
            return
        raise


def _ensure_required_labels(repo_slug: str, *, dry_run: bool) -> None:
    existing = _list_repo_labels(repo_slug)
    for name, spec in REQUIRED_LABEL_SPECS.items():
        if name in existing:
            continue
        _create_label(repo_slug, name, spec["color"], spec["description"], dry_run=dry_run)


def _is_readme_path(path: str) -> bool:
    return bool(re.search(r"(^|/)README[^/]*$", path, flags=re.IGNORECASE))


def _is_docs_path(path: str) -> bool:
    return path.startswith("docs/") or _is_readme_path(path)


def _is_engine_path(path: str) -> bool:
    return path.startswith("src/ji_engine/") or path.startswith("src/jobintel/")


def _is_provider_path(path: str) -> bool:
    return path.startswith("src/ji_engine/providers/")


def _is_dr_path(path: str) -> bool:
    return path.startswith("scripts/ops/") or path.startswith("ops/")


def _is_infra_path(path: str) -> bool:
    return path.startswith("ops/aws/") or path.startswith("ops/k8s/")


def _docs_only(paths: Sequence[str]) -> bool:
    return len(paths) > 0 and all(_is_docs_path(path) for path in paths)


def _choose_provenance(head_ref: str) -> str:
    if head_ref.startswith("codex/"):
        return "from-codex"
    if head_ref.startswith("composer/"):
        return "from-composer"
    return "from-human"


def _choose_type(title: str, changed_paths: Sequence[str]) -> str:
    trimmed = title.strip()
    if _docs_only(changed_paths) or re.match(r"^docs(?:\(|:)", trimmed, flags=re.IGNORECASE):
        return "type:docs"
    if re.match(r"^fix(?:\(|:)", trimmed, flags=re.IGNORECASE):
        return "type:fix"
    if re.match(r"^feat(?:\(|:)", trimmed, flags=re.IGNORECASE):
        return "type:feat"
    return "type:chore"


def _normalize_area_labels(labels: Iterable[str]) -> set[str]:
    out = {label for label in labels if label.startswith("area:")}
    non_docs_specific = {label for label in out if label not in {"area:docs", "area:unknown"}}
    if non_docs_specific:
        out.discard("area:docs")
    if "area:unknown" in out and len(out) > 1:
        out.discard("area:unknown")
    if not out:
        out = {"area:unknown"}
    return out


def _infer_areas(changed_paths: Sequence[str]) -> set[str]:
    inferred: set[str] = set()
    if any(_is_docs_path(path) for path in changed_paths):
        inferred.add("area:docs")
    if any(_is_engine_path(path) for path in changed_paths):
        inferred.add("area:engine")
    if any(_is_provider_path(path) for path in changed_paths):
        inferred.add("area:providers")
    if any(_is_dr_path(path) for path in changed_paths):
        inferred.add("area:dr")
    if any(_is_infra_path(path) for path in changed_paths):
        inferred.add("area:infra")
    if not inferred:
        inferred.add("area:unknown")
    return _normalize_area_labels(inferred)


def _ordered_areas(area_labels: Iterable[str]) -> list[str]:
    order = {label: idx for idx, label in enumerate(AREA_LABEL_ORDER)}
    return sorted(area_labels, key=lambda label: (order.get(label, 999), label))


def _dedupe_preserve_order(labels: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if label in seen:
            continue
        seen.add(label)
        out.append(label)
    return out


def _mentions_milestone_25(text: str) -> bool:
    return bool(re.search(r"\bMilestone\s*25\b|\bM25\b", text, flags=re.IGNORECASE))


def _extract_milestone_refs(text: str) -> list[int]:
    refs: list[int] = []
    for match in re.finditer(r"\bMilestone\s*(\d+)\b", text, flags=re.IGNORECASE):
        refs.append(int(match.group(1)))
    for match in re.finditer(r"\bM(\d+)\b", text, flags=re.IGNORECASE):
        refs.append(int(match.group(1)))
    # Stable de-duplication while preserving first-seen order.
    out: list[int] = []
    seen: set[int] = set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        out.append(ref)
    return out


def _nearest_milestone_title(
    text: str,
    milestones_by_title: dict[str, int],
    *,
    fallback_title: str,
) -> str:
    for ref in _extract_milestone_refs(text):
        candidate = f"M{ref}"
        if candidate in milestones_by_title:
            return candidate
    if fallback_title in milestones_by_title:
        return fallback_title

    numeric_titles = sorted(
        (title for title in milestones_by_title if re.fullmatch(r"M\d+", title)),
        key=lambda title: int(title[1:]),
    )
    if numeric_titles:
        return numeric_titles[0]
    raise CliError("no numeric roadmap milestone exists for fallback")


def _choose_milestone(
    *,
    title: str,
    body: str,
    docs_only: bool,
    existing_title: str | None,
    milestones_by_title: dict[str, int],
    current_hardening: str,
) -> MilestoneDecision:
    text = f"{title}\n{body}"
    if _mentions_milestone_25(text):
        return MilestoneDecision("M25", "explicit Milestone 25 marker", True)

    if docs_only:
        if DOCS_BUCKET in milestones_by_title:
            return MilestoneDecision(DOCS_BUCKET, "docs-only bucket", True)
        nearest = _nearest_milestone_title(text, milestones_by_title, fallback_title=current_hardening)
        return MilestoneDecision(nearest, "docs-only fallback to nearest roadmap milestone", True)

    if "(governance)" in title.lower():
        if INFRA_BUCKET in milestones_by_title:
            return MilestoneDecision(INFRA_BUCKET, "governance title bucket", True)
        fallback = _nearest_milestone_title(text, milestones_by_title, fallback_title=current_hardening)
        return MilestoneDecision(fallback, "governance title fallback to hardening milestone", True)

    if existing_title:
        return MilestoneDecision(existing_title, "preserve existing milestone", False)

    if BACKLOG_BUCKET in milestones_by_title:
        return MilestoneDecision(BACKLOG_BUCKET, "missing milestone default", True)

    fallback = _nearest_milestone_title(text, milestones_by_title, fallback_title=current_hardening)
    return MilestoneDecision(fallback, "missing bucket fallback to roadmap milestone", True)


def _extract_label_names(label_objects: object) -> list[str]:
    out: list[str] = []
    if not isinstance(label_objects, list):
        return out
    for item in label_objects:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                out.append(name.strip())
    return out


def _compute_final_labels(
    *,
    current_labels: Sequence[str],
    chosen_provenance: str,
    chosen_type: str,
    inferred_areas: set[str],
) -> list[str]:
    current_area = {label for label in current_labels if label.startswith("area:")}
    merged_area = _normalize_area_labels(current_area | inferred_areas)

    preserved = [
        label
        for label in current_labels
        if label not in PROVENANCE_LABELS and not label.startswith("type:") and not label.startswith("area:")
    ]

    final_labels = _dedupe_preserve_order(
        [
            *sorted(preserved),
            chosen_provenance,
            chosen_type,
            *_ordered_areas(merged_area),
        ]
    )
    return final_labels


def _apply_labels(repo_slug: str, pr_number: int, labels: Sequence[str], *, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN set-labels pr=#{pr_number} labels={','.join(labels)}")
        return
    _gh_api_json(repo_slug, f"issues/{pr_number}/labels", method="PUT", payload={"labels": list(labels)})


def _apply_milestone(
    repo_slug: str,
    pr_number: int,
    milestone_title: str,
    milestones_by_title: dict[str, int],
    *,
    dry_run: bool,
) -> None:
    if milestone_title not in milestones_by_title:
        raise CliError(f"missing milestone title required for apply: {milestone_title}")
    milestone_number = milestones_by_title[milestone_title]
    if dry_run:
        print(f"DRY-RUN set-milestone pr=#{pr_number} milestone={milestone_title}")
        return
    _gh_api_json(repo_slug, f"issues/{pr_number}", method="PATCH", payload={"milestone": milestone_number})


def _summarize_pr(pr: PrResult) -> str:
    milestone = pr.milestone if pr.milestone else "(none)"
    labels = ",".join(pr.labels)
    return f"PR #{pr.number} ok={str(pr.ok).lower()} milestone={milestone} labels=[{labels}] title={pr.title}"


def _verify_governance(labels: Sequence[str], milestone: str | None) -> bool:
    provenance_count = sum(1 for label in labels if label in PROVENANCE_LABELS)
    type_count = sum(1 for label in labels if label.startswith("type:"))
    area_count = sum(1 for label in labels if label.startswith("area:"))
    return provenance_count == 1 and type_count == 1 and area_count >= 1 and milestone is not None


def _process_open_prs(
    *,
    repo_slug: str,
    pr_numbers_filter: set[int],
    verify_only: bool,
    dry_run: bool,
    current_hardening: str,
) -> int:
    milestones_by_title = _list_repo_milestones(repo_slug)
    if not verify_only:
        _ensure_required_labels(repo_slug, dry_run=dry_run)

    open_prs = sorted(_gh_pr_list(repo_slug), key=lambda item: int(item.get("number", 0)))
    if pr_numbers_filter:
        open_prs = [item for item in open_prs if int(item.get("number", 0)) in pr_numbers_filter]

    print(
        f"repo={repo_slug} open_prs={len(open_prs)} verify_only={str(verify_only).lower()} dry_run={str(dry_run).lower()}"
    )

    results: list[PrResult] = []
    for pr in open_prs:
        number = int(pr.get("number", 0))
        title = str(pr.get("title") or "")
        body = str(pr.get("body") or "")
        head_ref = str(pr.get("headRefName") or "")

        changed_paths = _list_pr_files(repo_slug, number)
        docs_only = _docs_only(changed_paths)

        chosen_provenance = _choose_provenance(head_ref)
        chosen_type = _choose_type(title, changed_paths)
        inferred_areas = _infer_areas(changed_paths)

        issue = _fetch_pr_issue(repo_slug, number)
        current_labels = _extract_label_names(issue.get("labels"))

        milestone_obj = issue.get("milestone")
        existing_milestone = None
        if isinstance(milestone_obj, dict):
            milestone_title = milestone_obj.get("title")
            if isinstance(milestone_title, str) and milestone_title.strip():
                existing_milestone = milestone_title.strip()

        final_labels = _compute_final_labels(
            current_labels=current_labels,
            chosen_provenance=chosen_provenance,
            chosen_type=chosen_type,
            inferred_areas=inferred_areas,
        )
        milestone_decision = _choose_milestone(
            title=title,
            body=body,
            docs_only=docs_only,
            existing_title=existing_milestone,
            milestones_by_title=milestones_by_title,
            current_hardening=current_hardening,
        )

        labels_changed = set(final_labels) != set(current_labels)
        milestone_changed = milestone_decision.title != existing_milestone

        should_apply_milestone = False
        if milestone_decision.explicit_rule and milestone_changed:
            should_apply_milestone = True
        elif existing_milestone is None:
            should_apply_milestone = True

        if verify_only:
            print(
                f"VERIFY pr=#{number} provenance={chosen_provenance} type={chosen_type} "
                f"inferred_areas={','.join(_ordered_areas(inferred_areas))} milestone={existing_milestone or '(none)'}"
            )
        else:
            if labels_changed:
                _apply_labels(repo_slug, number, final_labels, dry_run=dry_run)
            if should_apply_milestone:
                _apply_milestone(
                    repo_slug,
                    number,
                    milestone_decision.title,
                    milestones_by_title,
                    dry_run=dry_run,
                )

            action = "noop"
            if labels_changed or milestone_changed:
                action = "updated"
            print(
                f"APPLY pr=#{number} action={action} provenance={chosen_provenance} type={chosen_type} "
                f"areas={','.join(_ordered_areas(inferred_areas))} milestone={milestone_decision.title} "
                f"reason={milestone_decision.reason}"
            )

        if dry_run and not verify_only:
            verified_labels = final_labels if labels_changed else current_labels
            verified_milestone = milestone_decision.title if should_apply_milestone else existing_milestone
        else:
            verified_issue = _fetch_pr_issue(repo_slug, number)
            verified_labels = _extract_label_names(verified_issue.get("labels"))
            verified_milestone_obj = verified_issue.get("milestone")
            verified_milestone = None
            if isinstance(verified_milestone_obj, dict):
                maybe_title = verified_milestone_obj.get("title")
                if isinstance(maybe_title, str) and maybe_title.strip():
                    verified_milestone = maybe_title.strip()

        ok = _verify_governance(verified_labels, verified_milestone)
        result = PrResult(
            number=number,
            title=title,
            labels=sorted(verified_labels),
            milestone=verified_milestone,
            ok=ok,
        )
        print(_summarize_pr(result))
        results.append(result)

    failed = [item for item in results if not item.ok]
    print("summary:")
    print(f"  total={len(results)}")
    print(f"  passing={len(results) - len(failed)}")
    print(f"  failing={len(failed)}")
    if failed:
        print("failing_prs:")
        for item in failed:
            print(f"  - #{item.number}")
        return 1
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply deterministic PR governance labels and milestones.")
    parser.add_argument("--repo", help="GitHub repo slug owner/name. Defaults to origin remote.")
    parser.add_argument("--apply-open-prs", action="store_true", help="Apply governance to currently open PRs.")
    parser.add_argument("--verify-only", action="store_true", help="Verify only, do not apply changes.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without mutating PR metadata.")
    parser.add_argument("--pr", action="append", type=int, default=[], help="Optional PR number filter (repeatable).")
    parser.add_argument(
        "--current-hardening",
        default="M22",
        help="Fallback hardening milestone title for governance/docs fallback paths (default: M22).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.apply_open_prs:
        print("ERROR: this script currently requires --apply-open-prs")
        return 2

    try:
        repo_slug = _resolve_repo_slug(args.repo)
        return _process_open_prs(
            repo_slug=repo_slug,
            pr_numbers_filter=set(args.pr),
            verify_only=args.verify_only,
            dry_run=args.dry_run,
            current_hardening=args.current_hardening,
        )
    except CliError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
