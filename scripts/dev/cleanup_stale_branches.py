#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

INCLUDE_PREFIXES = ("codex/", "composer/", "wip/", "tmp/", "fix/", "feat/", "chore/")
EXCLUDE_PREFIXES = ("release/", "dependabot/")
EXCLUDE_EXACT = {"main", "master"}


class BranchCleanupError(RuntimeError):
    """Raised when stale branch cleanup cannot continue safely."""


@dataclass(frozen=True)
class PrInfo:
    state: str
    number: int | None
    url: str | None


@dataclass(frozen=True)
class RemoteDecision:
    branch: str
    unique_commits: int
    merged: bool
    cherry_picked: bool
    pr_state: str
    last_commit_age_days: int
    action: str
    reason: str


@dataclass(frozen=True)
class LocalDecision:
    branch: str
    upstream: str
    action: str
    reason: str
    used_force: bool


def _run(cmd: Sequence[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, input=input_text)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "(no stderr)"
        raise BranchCleanupError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    return proc.stdout


def _run_status(cmd: Sequence[str]) -> int:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return proc.returncode


def _resolve_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo.strip()
    remote_url = _run(["git", "config", "--get", "remote.origin.url"]).strip()
    if not remote_url:
        raise BranchCleanupError("could not resolve repository from git remote.origin.url")

    import re

    https_match = re.match(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    ssh_match = re.match(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    match = https_match or ssh_match
    if not match:
        raise BranchCleanupError(f"unsupported GitHub remote URL format: {remote_url}")
    return f"{match.group('owner')}/{match.group('repo')}"


def _fetch_all() -> None:
    try:
        _run(["git", "fetch", "--all", "--prune", "--tags", "--no-write-fetch-head"])
    except BranchCleanupError as exc:
        text = str(exc)
        if "Operation not permitted" in text and "refs/remotes/origin" in text:
            # Sandbox fallback: refresh refs/tags without prune lock writes.
            _run(["git", "fetch", "--all", "--tags", "--no-write-fetch-head"])
            return
        raise


def _list_remote_branches(repo_slug: str) -> list[str]:
    page = 1
    branches: list[str] = []
    while True:
        payload = _run(["gh", "api", f"repos/{repo_slug}/branches?per_page=100&page={page}"])
        decoded = json.loads(payload)
        if not isinstance(decoded, list):
            raise BranchCleanupError("unexpected gh api branches response shape")
        if not decoded:
            break
        for item in decoded:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                branches.append(name.strip())
        page += 1
    return sorted(set(branches))


def _is_candidate_remote_branch(branch: str) -> bool:
    if branch in EXCLUDE_EXACT:
        return False
    if any(branch.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    return any(branch.startswith(prefix) for prefix in INCLUDE_PREFIXES)


def _list_all_pr_rows(repo_slug: str) -> list[dict[str, object]]:
    raw = _run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo_slug,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,state,mergedAt,closedAt,title,url,headRefName",
        ]
    )
    import json

    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise BranchCleanupError("unexpected gh pr list response")
    return [item for item in payload if isinstance(item, dict)]


def _select_pr_info(pr_rows: list[dict[str, object]]) -> PrInfo:
    if not pr_rows:
        return PrInfo(state="none", number=None, url=None)

    def _pr_number(item: dict[str, object]) -> int:
        value = item.get("number")
        return int(value) if isinstance(value, int) else 0

    open_prs = [item for item in pr_rows if str(item.get("state") or "").upper() == "OPEN"]
    if open_prs:
        chosen = max(open_prs, key=_pr_number)
        return PrInfo(state="open", number=_pr_number(chosen), url=str(chosen.get("url") or ""))

    merged_prs = [item for item in pr_rows if item.get("mergedAt")]
    if merged_prs:
        chosen = max(merged_prs, key=_pr_number)
        return PrInfo(state="merged", number=_pr_number(chosen), url=str(chosen.get("url") or ""))

    closed_prs = [item for item in pr_rows if str(item.get("state") or "").upper() == "CLOSED"]
    if closed_prs:
        chosen = max(closed_prs, key=_pr_number)
        return PrInfo(state="closed", number=_pr_number(chosen), url=str(chosen.get("url") or ""))

    return PrInfo(state="none", number=None, url=None)


def _build_pr_map(repo_slug: str) -> dict[str, PrInfo]:
    rows = _list_all_pr_rows(repo_slug)
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        head_ref = row.get("headRefName")
        if not isinstance(head_ref, str) or not head_ref.strip():
            continue
        grouped.setdefault(head_ref.strip(), []).append(row)

    out: dict[str, PrInfo] = {}
    for branch, items in grouped.items():
        out[branch] = _select_pr_info(items)
    return out


def _is_ancestor(commitish: str, base: str) -> bool:
    return _run_status(["git", "merge-base", "--is-ancestor", commitish, base]) == 0


def _unique_commits(base: str, branch_ref: str) -> list[str]:
    raw = _run(["git", "rev-list", f"{base}..{branch_ref}"])
    out = [line.strip() for line in raw.splitlines() if line.strip()]
    return out


def _commit_contained_in_main(sha: str) -> bool:
    raw = _run(["git", "branch", "-r", "--contains", sha])
    refs = {line.strip().lstrip("*").strip() for line in raw.splitlines() if line.strip()}
    return "origin/main" in refs


def _last_commit_age_days(branch_ref: str, now_epoch: int) -> int:
    raw = _run(["git", "show", "-s", "--format=%ct", branch_ref]).strip()
    try:
        ts = int(raw)
    except ValueError as exc:
        raise BranchCleanupError(f"invalid commit timestamp for {branch_ref}: {raw}") from exc
    age = max(0, now_epoch - ts)
    return age // 86400


def _decide_remote_branch(
    *,
    branch: str,
    pr_info: PrInfo,
    review_days: int,
    now_epoch: int,
) -> RemoteDecision:
    branch_ref = f"origin/{branch}"
    merged = _is_ancestor(branch_ref, "origin/main")
    unique = _unique_commits("origin/main", branch_ref)
    unique_count = len(unique)
    cherry_picked = all(_commit_contained_in_main(sha) for sha in unique)
    age_days = _last_commit_age_days(branch_ref, now_epoch)

    no_open_pr = pr_info.state != "open"

    if no_open_pr and (merged or cherry_picked):
        reason = "merged-into-main" if merged else "all-unique-commits-contained-in-main"
        return RemoteDecision(
            branch=branch,
            unique_commits=unique_count,
            merged=merged,
            cherry_picked=cherry_picked,
            pr_state=pr_info.state,
            last_commit_age_days=age_days,
            action="delete",
            reason=reason,
        )

    if pr_info.state == "open":
        return RemoteDecision(
            branch=branch,
            unique_commits=unique_count,
            merged=merged,
            cherry_picked=cherry_picked,
            pr_state=pr_info.state,
            last_commit_age_days=age_days,
            action="keep",
            reason="open-pr",
        )

    if pr_info.state == "none" and age_days < review_days:
        return RemoteDecision(
            branch=branch,
            unique_commits=unique_count,
            merged=merged,
            cherry_picked=cherry_picked,
            pr_state=pr_info.state,
            last_commit_age_days=age_days,
            action="review",
            reason="recent-without-pr",
        )

    return RemoteDecision(
        branch=branch,
        unique_commits=unique_count,
        merged=merged,
        cherry_picked=cherry_picked,
        pr_state=pr_info.state,
        last_commit_age_days=age_days,
        action="keep",
        reason="contains-commits-not-in-main",
    )


def _ensure_remote_ref(branch: str) -> None:
    ref = f"origin/{branch}"
    if _run_status(["git", "rev-parse", "--verify", ref]) == 0:
        return
    _run(
        [
            "git",
            "fetch",
            "origin",
            "--no-tags",
            "--no-write-fetch-head",
            f"refs/heads/{branch}:refs/remotes/origin/{branch}",
        ]
    )


def _list_local_branches() -> list[tuple[str, str]]:
    raw = _run(["git", "for-each-ref", "refs/heads", "--format=%(refname:short)|%(upstream:short)"])
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if "|" not in line:
            continue
        branch, upstream = line.split("|", 1)
        out.append((branch.strip(), upstream.strip()))
    return sorted(out)


def _delete_remote_branch(branch: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN remote-delete origin/{branch}")
        return
    _run(["git", "push", "origin", "--delete", branch])


def _delete_local_branch(branch: str, *, force: bool, dry_run: bool) -> None:
    if dry_run:
        flag = "-D" if force else "-d"
        print(f"DRY-RUN local-delete {flag} {branch}")
        return
    flag = "-D" if force else "-d"
    _run(["git", "branch", flag, branch])


def _render_bool(value: bool) -> str:
    return "yes" if value else "no"


def _print_remote_table(decisions: list[RemoteDecision]) -> None:
    print("branch | unique_commits | merged? | cherry_picked? | pr_state | last_commit_age_days | action")
    print("--- | ---: | :---: | :---: | :---: | ---: | :---:")
    for d in decisions:
        print(
            f"{d.branch} | {d.unique_commits} | {_render_bool(d.merged)} | "
            f"{_render_bool(d.cherry_picked)} | {d.pr_state} | {d.last_commit_age_days} | {d.action}"
        )


def _write_report(
    path: Path,
    *,
    mode: str,
    generated_at: str,
    decisions: list[RemoteDecision],
    local_decisions: list[LocalDecision],
) -> None:
    scanned = len(decisions)
    deleted_remote = sum(1 for d in decisions if d.action == "delete")
    kept = sum(1 for d in decisions if d.action == "keep")
    review_needed = sum(1 for d in decisions if d.action == "review")
    deleted_local = sum(1 for d in local_decisions if d.action == "delete")

    lines: list[str] = []
    lines.append(f"# Branch Cleanup Report ({generated_at[:10]})")
    lines.append("")
    lines.append(f"- mode: `{mode}`")
    lines.append(f"- scanned: `{scanned}`")
    lines.append(f"- deleted_remote: `{deleted_remote}`")
    lines.append(f"- deleted_local: `{deleted_local}`")
    lines.append(f"- kept: `{kept}`")
    lines.append(f"- review_needed: `{review_needed}`")
    lines.append("")
    lines.append("## Remote Branch Decisions")
    lines.append("")
    lines.append(
        "branch | unique_commits | merged? | cherry_picked? | pr_state | last_commit_age_days | action | reason"
    )
    lines.append("--- | ---: | :---: | :---: | :---: | ---: | :---: | ---")
    for d in decisions:
        lines.append(
            f"{d.branch} | {d.unique_commits} | {_render_bool(d.merged)} | {_render_bool(d.cherry_picked)} | "
            f"{d.pr_state} | {d.last_commit_age_days} | {d.action} | {d.reason}"
        )
    lines.append("")
    lines.append("## Local Branch Decisions")
    lines.append("")
    lines.append("branch | upstream | action | force? | reason")
    lines.append("--- | --- | :---: | :---: | ---")
    if local_decisions:
        for d in local_decisions:
            lines.append(
                f"{d.branch} | {d.upstream or '(none)'} | {d.action} | {_render_bool(d.used_force)} | {d.reason}"
            )
    else:
        lines.append("(none)")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic stale branch cleanup (remote + local) using git/gh.")
    parser.add_argument("--repo", default=None, help="GitHub repository slug (<owner>/<repo>).")
    parser.add_argument("--apply", action="store_true", help="Apply deletions. Default is dry-run.")
    parser.add_argument("--review-days", type=int, default=7, help="Recent branch threshold in days (default: 7).")
    parser.add_argument("--report", default=None, help="Optional markdown report output path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "apply" if args.apply else "dry-run"
    report_path = Path(args.report) if args.report else None

    try:
        repo_slug = _resolve_repo_slug(args.repo)
        _fetch_all()

        # Ensure canonical base ref exists.
        _run(["git", "rev-parse", "--verify", "origin/main"])

        pr_map = _build_pr_map(repo_slug)
        now_epoch = int(time.time())
        generated_at = datetime.now(timezone.utc).isoformat()

        candidate_branches = [b for b in _list_remote_branches(repo_slug) if _is_candidate_remote_branch(b)]

        remote_decisions: list[RemoteDecision] = []
        for branch in candidate_branches:
            _ensure_remote_ref(branch)
            info = pr_map.get(branch, PrInfo(state="none", number=None, url=None))
            decision = _decide_remote_branch(
                branch=branch, pr_info=info, review_days=args.review_days, now_epoch=now_epoch
            )
            remote_decisions.append(decision)

        remote_decisions = sorted(remote_decisions, key=lambda d: d.branch)
        _print_remote_table(remote_decisions)

        deleted_remote: set[str] = set()
        remote_redundant: set[str] = set()
        for d in remote_decisions:
            if d.action != "delete":
                continue
            _delete_remote_branch(d.branch, dry_run=not args.apply)
            deleted_remote.add(d.branch)
            remote_redundant.add(d.branch)

        current_branch = _run(["git", "branch", "--show-current"]).strip()
        local_decisions: list[LocalDecision] = []

        for branch, upstream in _list_local_branches():
            if branch in {"main", current_branch}:
                continue

            tracked_remote_deleted = upstream.startswith("origin/") and upstream.split("/", 1)[1] in deleted_remote
            merged_local = _is_ancestor(branch, "origin/main")
            if not tracked_remote_deleted and not merged_local:
                local_decisions.append(
                    LocalDecision(
                        branch=branch,
                        upstream=upstream,
                        action="keep",
                        reason="not-merged-or-tracked-remote-kept",
                        used_force=False,
                    )
                )
                continue

            # Safe default is -d. Use -D only for proven redundant remote branches (rule A).
            force_allowed = bool(upstream.startswith("origin/") and upstream.split("/", 1)[1] in remote_redundant)
            used_force = False
            if args.apply:
                try:
                    _delete_local_branch(branch, force=False, dry_run=False)
                except BranchCleanupError:
                    if force_allowed:
                        _delete_local_branch(branch, force=True, dry_run=False)
                        used_force = True
                    else:
                        local_decisions.append(
                            LocalDecision(
                                branch=branch,
                                upstream=upstream,
                                action="keep",
                                reason="safe-delete-failed",
                                used_force=False,
                            )
                        )
                        continue
            else:
                _delete_local_branch(branch, force=force_allowed, dry_run=True)
                used_force = force_allowed

            reason = "tracking-deleted-remote" if tracked_remote_deleted else "fully-merged-into-main"
            local_decisions.append(
                LocalDecision(
                    branch=branch,
                    upstream=upstream,
                    action="delete",
                    reason=reason,
                    used_force=used_force,
                )
            )

        local_decisions = sorted(local_decisions, key=lambda d: d.branch)

        scanned = len(remote_decisions)
        deleted_remote_count = sum(1 for d in remote_decisions if d.action == "delete")
        kept_count = sum(1 for d in remote_decisions if d.action == "keep")
        review_count = sum(1 for d in remote_decisions if d.action == "review")
        deleted_local_count = sum(1 for d in local_decisions if d.action == "delete")

        print("BRANCH_CLEANUP_SUMMARY")
        print(f"mode: {mode}")
        print(f"repo: {repo_slug}")
        print(f"scanned: {scanned}")
        print(f"deleted_remote: {deleted_remote_count}")
        print(f"deleted_local: {deleted_local_count}")
        print(f"kept: {kept_count}")
        print(f"review_needed: {review_count}")

        if report_path is not None:
            _write_report(
                report_path,
                mode=mode,
                generated_at=generated_at,
                decisions=remote_decisions,
                local_decisions=local_decisions,
            )
            print(f"report: {report_path}")

        print("BRANCH_CLEANUP_OK")
        return 0
    except BranchCleanupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
