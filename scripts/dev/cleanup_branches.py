#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

REMOTE_PATTERNS = (
    re.compile(r"^codex/"),
    re.compile(r"^composer/"),
    re.compile(r"^tmp/"),
    re.compile(r"^wip/"),
)


class BranchCleanupError(RuntimeError):
    """Raised when branch cleanup cannot safely continue."""


@dataclass(frozen=True)
class RemoteDecision:
    branch: str
    action: str
    reason: str


@dataclass(frozen=True)
class LocalDecision:
    branch: str
    action: str
    reason: str


def _run(cmd: list[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, input=input_text)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "(no stderr)"
        raise BranchCleanupError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    return proc.stdout


def _resolve_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo.strip()
    remote_url = _run(["git", "config", "--get", "remote.origin.url"]).strip()
    if not remote_url:
        raise BranchCleanupError("could not resolve repository from git remote.origin.url")
    https_match = re.match(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    ssh_match = re.match(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    match = https_match or ssh_match
    if not match:
        raise BranchCleanupError(f"unsupported GitHub remote URL format: {remote_url}")
    return f"{match.group('owner')}/{match.group('repo')}"


def _gh_api_json(path: str, *, method: str = "GET") -> object:
    cmd = ["gh", "api", path]
    if method != "GET":
        cmd.extend(["--method", method])
    raw = _run(cmd).strip()
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
            raise BranchCleanupError(f"unexpected paginated response for {path}")
        if not payload:
            return out
        out.extend(item for item in payload if isinstance(item, dict))
        page += 1


def _is_candidate_remote(name: str) -> bool:
    return any(pattern.search(name) for pattern in REMOTE_PATTERNS)


def _search_total_count(query: str) -> int:
    payload = _gh_api_json(f"search/issues?q={quote(query)}&per_page=1")
    if not isinstance(payload, dict):
        raise BranchCleanupError("unexpected search response shape")
    count = payload.get("total_count")
    if not isinstance(count, int):
        raise BranchCleanupError("missing total_count in search response")
    return count


def _remote_open_pr_count(repo_slug: str, owner: str, branch: str) -> int:
    query = f"repo:{repo_slug} is:pr is:open head:{owner}:{branch}"
    return _search_total_count(query)


def _remote_merged_pr_count(repo_slug: str, owner: str, branch: str) -> int:
    query = f"repo:{repo_slug} is:pr is:merged head:{owner}:{branch}"
    return _search_total_count(query)


def _remote_branch_merged_into_main(repo_slug: str, branch: str) -> bool:
    encoded = quote(branch, safe="")
    payload = _gh_api_json(f"repos/{repo_slug}/compare/main...{encoded}")
    if not isinstance(payload, dict):
        raise BranchCleanupError("unexpected compare response")
    status = payload.get("status")
    if not isinstance(status, str):
        raise BranchCleanupError("missing compare status")
    return status in {"behind", "identical"}


def _delete_remote_branch(repo_slug: str, branch: str) -> None:
    encoded = quote(branch, safe="")
    _gh_api_json(f"repos/{repo_slug}/git/refs/heads/{encoded}", method="DELETE")


def _local_branch_rows() -> list[tuple[str, str]]:
    raw = _run(["git", "for-each-ref", "refs/heads", "--format=%(refname:short)|%(upstream:short)"])
    rows: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if "|" not in line:
            continue
        branch, upstream = line.split("|", 1)
        rows.append((branch.strip(), upstream.strip()))
    return rows


def _local_is_merged(branch: str) -> bool:
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", branch, "main"], check=False)
    return proc.returncode == 0


def _remote_ref_exists(upstream: str) -> bool:
    proc = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/{upstream}"], check=False)
    return proc.returncode == 0


def _remote_branch_exists(repo_slug: str, branch: str) -> bool:
    encoded = quote(branch, safe="")
    proc = subprocess.run(
        ["gh", "api", f"repos/{repo_slug}/branches/{encoded}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return True
    stderr = (proc.stderr or "").lower()
    stdout = (proc.stdout or "").lower()
    if "not found" in stderr or "not found" in stdout or "404" in stderr or "404" in stdout:
        return False
    raise BranchCleanupError(
        f"failed checking remote branch existence for {branch}: "
        f"{proc.stderr.strip() or proc.stdout.strip() or '(no stderr)'}"
    )


def _write_report(
    path: Path,
    *,
    repo_slug: str,
    mode: str,
    remote_decisions: list[RemoteDecision],
    local_decisions: list[LocalDecision],
) -> None:
    lines: list[str] = []
    lines.append("# Branch Cleanup Report")
    lines.append("")
    lines.append(f"- repo: `{repo_slug}`")
    lines.append(f"- mode: `{mode}`")
    lines.append("")
    lines.append("## Remote Decisions")
    for d in remote_decisions:
        lines.append(f"- `{d.branch}` action=`{d.action}` reason=`{d.reason}`")
    if not remote_decisions:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Local Decisions")
    for d in local_decisions:
        lines.append(f"- `{d.branch}` action=`{d.action}` reason=`{d.reason}`")
    if not local_decisions:
        lines.append("- (none)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Programmatic remote/local stale branch cleanup.")
    parser.add_argument("--repo", default=None, help="GitHub repository slug (<owner>/<repo>).")
    parser.add_argument("--apply", action="store_true", help="Apply deletions. Default is dry-run.")
    parser.add_argument("--skip-remote", action="store_true", help="Skip remote branch cleanup pass.")
    parser.add_argument("--skip-local", action="store_true", help="Skip local branch cleanup pass.")
    parser.add_argument("--report", default=None, help="Optional markdown report path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "apply" if args.apply else "dry-run"
    report_path = Path(args.report) if args.report else None
    try:
        if args.skip_remote and args.skip_local:
            raise BranchCleanupError("cannot use both --skip-remote and --skip-local")
        repo_slug = _resolve_repo_slug(args.repo)
        owner = repo_slug.split("/", 1)[0]
        current_branch = _run(["git", "branch", "--show-current"]).strip()

        remote_decisions: list[RemoteDecision] = []
        if not args.skip_remote:
            remote_rows = _list_paginated(f"repos/{repo_slug}/branches?per_page=100")
            for row in remote_rows:
                name = row.get("name")
                if not isinstance(name, str) or not _is_candidate_remote(name):
                    continue
                open_prs = _remote_open_pr_count(repo_slug, owner, name)
                if open_prs > 0:
                    remote_decisions.append(RemoteDecision(branch=name, action="keep", reason="has-open-pr"))
                    continue
                merged_prs = _remote_merged_pr_count(repo_slug, owner, name)
                merged_into_main = _remote_branch_merged_into_main(repo_slug, name)
                if merged_prs > 0 or merged_into_main:
                    if args.apply:
                        _delete_remote_branch(repo_slug, name)
                    reason = "has-merged-pr" if merged_prs > 0 else "fully-merged-into-main"
                    remote_decisions.append(RemoteDecision(branch=name, action="delete", reason=reason))
                else:
                    remote_decisions.append(RemoteDecision(branch=name, action="keep", reason="unmerged-no-merged-pr"))

        local_decisions: list[LocalDecision] = []
        if not args.skip_local:
            for branch, upstream in _local_branch_rows():
                if branch == "main":
                    local_decisions.append(LocalDecision(branch=branch, action="keep", reason="main"))
                    continue
                if branch == current_branch:
                    local_decisions.append(LocalDecision(branch=branch, action="keep", reason="checked-out"))
                    continue
                merged = _local_is_merged(branch)
                upstream_exists = False
                if upstream:
                    upstream_exists = _remote_ref_exists(upstream)
                    if not upstream_exists and upstream.startswith("origin/"):
                        upstream_exists = _remote_branch_exists(repo_slug, upstream.split("/", 1)[1])
                if merged and not upstream_exists:
                    if args.apply:
                        _run(["git", "branch", "-d", branch])
                    local_decisions.append(
                        LocalDecision(branch=branch, action="delete", reason="merged-upstream-missing")
                    )
                else:
                    reason = "unmerged" if not merged else "upstream-present"
                    local_decisions.append(LocalDecision(branch=branch, action="keep", reason=reason))

        print("BRANCH_CLEANUP_SUMMARY")
        print(f"mode: {mode}")
        print(f"repo: {repo_slug}")
        print(f"remote_delete_count: {sum(1 for d in remote_decisions if d.action == 'delete')}")
        print(f"local_delete_count: {sum(1 for d in local_decisions if d.action == 'delete')}")
        for d in sorted(remote_decisions, key=lambda item: item.branch):
            print(f"remote branch={d.branch} action={d.action} reason={d.reason}")
        for d in sorted(local_decisions, key=lambda item: item.branch):
            print(f"local branch={d.branch} action={d.action} reason={d.reason}")

        if report_path is not None:
            _write_report(
                report_path,
                repo_slug=repo_slug,
                mode=mode,
                remote_decisions=remote_decisions,
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
