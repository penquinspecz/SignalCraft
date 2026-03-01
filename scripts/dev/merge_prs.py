#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

PASS_CHECK_STATES = {"SUCCESS", "NEUTRAL", "SKIPPED"}
PENDING_CHECK_STATES = {"PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "WAITING", "REQUESTED"}
DEFAULT_SUPERSEDES = {258: 261}
POLICY_DOCS = ("CONTRIBUTING.md", "docs/BRANCHING.md", "docs/RELEASE_PROCESS.md")


class CliError(RuntimeError):
    """User-facing, stable command/validation failures."""


@dataclass(frozen=True)
class CheckState:
    ok: bool
    pending: bool
    message: str


@dataclass(frozen=True)
class PRMeta:
    number: int
    title: str
    url: str
    state: str
    is_draft: bool
    mergeable: str
    merge_state_status: str


@dataclass(frozen=True)
class MergePlanItem:
    number: int
    reason: str


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


def _gh_json(args: Sequence[str]) -> object:
    raw = _run(["gh", *args]).strip()
    if not raw:
        return {}
    return json.loads(raw)


def _gh_pr_view(repo_slug: str, pr_number: int) -> PRMeta:
    payload = _gh_json(
        [
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo_slug,
            "--json",
            "number,title,url,state,isDraft,mergeable,mergeStateStatus",
        ]
    )
    if not isinstance(payload, dict):
        raise CliError(f"unexpected gh pr view response for #{pr_number}")

    return PRMeta(
        number=int(payload.get("number", pr_number)),
        title=str(payload.get("title") or ""),
        url=str(payload.get("url") or ""),
        state=str(payload.get("state") or ""),
        is_draft=bool(payload.get("isDraft")),
        mergeable=str(payload.get("mergeable") or ""),
        merge_state_status=str(payload.get("mergeStateStatus") or ""),
    )


def _gh_pr_checks_required(repo_slug: str, pr_number: int) -> list[dict[str, str]]:
    payload = _gh_json(
        [
            "pr",
            "checks",
            str(pr_number),
            "--repo",
            repo_slug,
            "--required",
            "--json",
            "name,state,workflow,link",
        ]
    )
    if not isinstance(payload, list):
        raise CliError(f"unexpected gh pr checks response for #{pr_number}")

    checks: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        checks.append(
            {
                "name": str(item.get("name") or ""),
                "state": str(item.get("state") or ""),
                "workflow": str(item.get("workflow") or ""),
                "link": str(item.get("link") or ""),
            }
        )
    return checks


def _evaluate_checks(checks: Sequence[dict[str, str]]) -> CheckState:
    if not checks:
        return CheckState(False, False, "no required checks returned by gh pr checks --required")

    failures: list[str] = []
    pending: list[str] = []

    pr_gov_states = [
        check["state"] for check in checks if check["name"] == "pr-governance" or check["workflow"] == "pr-governance"
    ]
    if not pr_gov_states:
        return CheckState(False, False, "required check pr-governance not found")

    for check in checks:
        state = check["state"]
        label = f"{check['workflow']}/{check['name']}"
        if state in PASS_CHECK_STATES:
            continue
        if state in PENDING_CHECK_STATES:
            pending.append(f"{label}:{state}")
            continue
        failures.append(f"{label}:{state}")

    if any(state != "SUCCESS" for state in pr_gov_states):
        if any(state in PENDING_CHECK_STATES for state in pr_gov_states):
            pending.append("pr-governance:pending")
        else:
            failures.append(f"pr-governance:{','.join(pr_gov_states)}")

    if failures:
        return CheckState(False, False, "failing checks: " + "; ".join(sorted(set(failures))))
    if pending:
        return CheckState(False, True, "pending checks: " + "; ".join(sorted(set(pending))))
    return CheckState(True, False, "all required checks green")


def _wait_for_checks(repo_slug: str, pr_number: int, timeout_sec: int, poll_sec: int) -> None:
    deadline = time.time() + timeout_sec
    while True:
        checks = _gh_pr_checks_required(repo_slug, pr_number)
        state = _evaluate_checks(checks)
        if state.ok:
            return

        if state.pending and time.time() < deadline:
            print(f"PR #{pr_number}: waiting for checks ({state.message})")
            time.sleep(poll_sec)
            continue

        if state.pending:
            raise CliError(f"PR #{pr_number}: checks did not finish before timeout ({state.message})")
        raise CliError(f"PR #{pr_number}: checks not green ({state.message})")


def _ensure_mergeable(meta: PRMeta, pr_number: int) -> None:
    if meta.state != "OPEN":
        raise CliError(f"PR #{pr_number}: expected OPEN state, found {meta.state}")
    if meta.is_draft:
        raise CliError(f"PR #{pr_number}: draft PR cannot enter merge train")
    if meta.mergeable != "MERGEABLE":
        raise CliError(f"PR #{pr_number}: mergeable state is {meta.mergeable}, expected MERGEABLE")
    if meta.merge_state_status == "DIRTY":
        raise CliError(f"PR #{pr_number}: merge state is DIRTY (conflict)")


def _update_branch(repo_slug: str, pr_number: int, *, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN update-branch pr=#{pr_number}")
        return
    _run(["gh", "api", f"repos/{repo_slug}/pulls/{pr_number}/update-branch", "--method", "PUT"])
    print(f"PR #{pr_number}: branch update requested")


def _wait_for_mergeability(repo_slug: str, pr_number: int, timeout_sec: int, poll_sec: int) -> PRMeta:
    deadline = time.time() + timeout_sec
    while True:
        meta = _gh_pr_view(repo_slug, pr_number)
        if meta.mergeable != "UNKNOWN" and meta.merge_state_status != "UNKNOWN":
            return meta
        if time.time() >= deadline:
            raise CliError(f"PR #{pr_number}: mergeability remained UNKNOWN past timeout")
        print(f"PR #{pr_number}: waiting for mergeability computation")
        time.sleep(poll_sec)


def _load_merge_policy_method(explicit: str | None) -> tuple[str, str]:
    if explicit:
        return explicit, "explicit --method override"

    merged_text: list[str] = []
    scanned: list[str] = []
    for doc in POLICY_DOCS:
        path = Path(doc)
        if path.exists():
            scanned.append(doc)
            merged_text.append(path.read_text(encoding="utf-8").lower())

    full_text = "\n".join(merged_text)
    if re.search(r"\bsquash\b", full_text):
        return "squash", f"policy keyword 'squash' found in {', '.join(scanned)}"
    if re.search(r"\bmerge commit\b|\bmerge-commit\b", full_text):
        return "merge", f"policy keyword 'merge commit' found in {', '.join(scanned)}"
    return (
        "squash",
        f"no explicit merge method found in {', '.join(scanned) if scanned else 'policy docs'}; defaulting to squash",
    )


def _default_order_key(item: dict[str, object]) -> tuple[int, int]:
    number = int(item.get("number", 0))
    title = str(item.get("title") or "").lower()
    label_names = {str(label.get("name") or "") for label in (item.get("labels") or []) if isinstance(label, dict)}

    if "governance" in title or "tooling" in title or "area:infra" in label_names:
        tier = 0
    elif "roadmap" in title or "area:docs" in label_names or title.startswith("docs(") or title.startswith("docs:"):
        tier = 1
    elif "security" in title or "harden" in title or "ssrf" in title or "traversal" in title:
        tier = 3
    else:
        tier = 2
    return tier, number


def _list_open_prs(repo_slug: str) -> list[dict[str, object]]:
    payload = _gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo_slug,
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,labels",
        ]
    )
    if not isinstance(payload, list):
        raise CliError("unexpected gh pr list response")
    out: list[dict[str, object]] = []
    for item in payload:
        if isinstance(item, dict):
            out.append(item)
    return out


def _resolve_pr_sequence(repo_slug: str, prs: Sequence[int], config_path: str | None) -> list[int]:
    if prs:
        return [int(pr) for pr in prs]

    if config_path:
        payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("prs"), list):
            raise CliError("config must be an object with a 'prs' list")
        return [int(pr) for pr in payload["prs"]]

    open_prs = _list_open_prs(repo_slug)
    ordered = sorted(open_prs, key=_default_order_key)
    return [int(item.get("number", 0)) for item in ordered if int(item.get("number", 0)) > 0]


def _apply_supersedes(pr_numbers: Sequence[int], *, auto_skip: bool) -> tuple[list[int], list[MergePlanItem]]:
    selected = list(pr_numbers)
    notes: list[MergePlanItem] = []
    if not auto_skip:
        for older, newer in DEFAULT_SUPERSEDES.items():
            if older in selected and newer in selected:
                notes.append(
                    MergePlanItem(older, f"supersede mapping present but auto-skip disabled (newer PR #{newer})")
                )
        return selected, notes

    keep: list[int] = []
    selected_set = set(selected)
    for pr in selected:
        superseded_by = DEFAULT_SUPERSEDES.get(pr)
        if superseded_by and superseded_by in selected_set:
            notes.append(MergePlanItem(pr, f"skipped as superseded by PR #{superseded_by}"))
            continue
        keep.append(pr)
    return keep, notes


def _merge_pr(repo_slug: str, pr_number: int, method: str, *, delete_branch: bool, dry_run: bool) -> None:
    cmd = ["gh", "pr", "merge", str(pr_number), "--repo", repo_slug]
    if method == "squash":
        cmd.append("--squash")
    else:
        cmd.append("--merge")
    if delete_branch:
        cmd.append("--delete-branch")

    if dry_run:
        print(f"DRY-RUN merge-command: {' '.join(cmd)}")
        return
    _run(cmd)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic merge-train helper for ordered PR merging.")
    parser.add_argument("--repo", help="GitHub repo slug owner/name. Defaults to origin remote.")
    parser.add_argument("--prs", nargs="*", type=int, default=[], help="Ordered PR list to merge.")
    parser.add_argument("--config", help="Optional JSON config with {'prs': [..]}.")
    parser.add_argument("--method", choices=("squash", "merge"), help="Override merge method.")
    parser.add_argument("--delete-branch", action="store_true", help="Delete branch after successful merge.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without mutating GitHub state.")
    parser.add_argument(
        "--no-auto-supersede", action="store_true", help="Disable automatic skip of known superseded PRs."
    )
    parser.add_argument("--poll-sec", type=int, default=15, help="Polling interval in seconds (default: 15).")
    parser.add_argument(
        "--timeout-sec", type=int, default=1800, help="Max wait for checks/mergeability (default: 1800)."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        repo_slug = _resolve_repo_slug(args.repo)
        requested = _resolve_pr_sequence(repo_slug, args.prs, args.config)
        if not requested:
            raise CliError("no PRs selected for merge train")

        planned, notes = _apply_supersedes(requested, auto_skip=not args.no_auto_supersede)
        if not planned:
            raise CliError("all requested PRs were skipped by supersede rules")

        method, method_reason = _load_merge_policy_method(args.method)
        print(f"repo={repo_slug}")
        print(f"method={method} reason={method_reason}")
        print(f"delete_branch={str(args.delete_branch).lower()} dry_run={str(args.dry_run).lower()}")
        print("requested_order=" + " ".join(str(pr) for pr in requested))
        if notes:
            for item in notes:
                print(f"skip-note pr=#{item.number} reason={item.reason}")
        print("planned_order=" + " ".join(str(pr) for pr in planned))

        merged: list[int] = []
        for pr_number in planned:
            print(f"----\nPR #{pr_number}: validating")
            meta = _wait_for_mergeability(repo_slug, pr_number, args.timeout_sec, args.poll_sec)
            _ensure_mergeable(meta, pr_number)
            assumed_dry_run_update = False

            if meta.merge_state_status == "BEHIND":
                _update_branch(repo_slug, pr_number, dry_run=args.dry_run)
                if not args.dry_run:
                    meta = _wait_for_mergeability(repo_slug, pr_number, args.timeout_sec, args.poll_sec)
                else:
                    print(f"PR #{pr_number}: dry-run assumes branch update succeeds")
                    assumed_dry_run_update = True

            _wait_for_checks(repo_slug, pr_number, args.timeout_sec, args.poll_sec)

            meta = _wait_for_mergeability(repo_slug, pr_number, args.timeout_sec, args.poll_sec)
            _ensure_mergeable(meta, pr_number)
            if meta.merge_state_status == "BEHIND":
                if args.dry_run and assumed_dry_run_update:
                    print(f"PR #{pr_number}: dry-run continuing despite BEHIND after simulated update")
                    print(f"PR #{pr_number}: merging ({method})")
                    _merge_pr(repo_slug, pr_number, method, delete_branch=args.delete_branch, dry_run=args.dry_run)
                    merged.append(pr_number)
                    continue
                raise CliError(f"PR #{pr_number}: still BEHIND after update/check cycle")

            print(f"PR #{pr_number}: merging ({method})")
            _merge_pr(repo_slug, pr_number, method, delete_branch=args.delete_branch, dry_run=args.dry_run)
            merged.append(pr_number)

        print("----")
        print(f"merge-train complete merged_count={len(merged)}")
        print("merged_order=" + " ".join(str(pr) for pr in merged))
        return 0
    except CliError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
