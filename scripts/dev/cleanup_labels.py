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

MILESTONE_LABEL_RE = re.compile(r"^(m[0-9]+[a-z]?)|(milestone[: ]m[0-9]+.*)$", re.IGNORECASE)
PROTECTED_PREFIXES = ("from-", "type:", "area:", "planner:")


class LabelCleanupError(RuntimeError):
    """Raised when label cleanup cannot safely continue."""


@dataclass(frozen=True)
class LabelDecision:
    name: str
    reason: str
    open_issue_count: int
    open_pr_count: int
    action: str


def _run(cmd: list[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, input=input_text)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip() or "(no stderr)"
        raise LabelCleanupError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    return proc.stdout


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


def _resolve_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo.strip()
    remote_url = _run(["git", "config", "--get", "remote.origin.url"]).strip()
    if not remote_url:
        raise LabelCleanupError("could not resolve repository from git remote.origin.url")
    https_match = re.match(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    ssh_match = re.match(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote_url)
    match = https_match or ssh_match
    if not match:
        raise LabelCleanupError(f"unsupported GitHub remote URL format: {remote_url}")
    return f"{match.group('owner')}/{match.group('repo')}"


def _list_paginated(path: str) -> list[dict[str, object]]:
    page = 1
    out: list[dict[str, object]] = []
    while True:
        endpoint = f"{path}&page={page}" if "?" in path else f"{path}?page={page}"
        payload = _gh_api_json(endpoint)
        if not isinstance(payload, list):
            raise LabelCleanupError(f"unexpected paginated response for {path}")
        if not payload:
            return out
        out.extend(item for item in payload if isinstance(item, dict))
        page += 1


def _list_labels(repo_slug: str) -> list[str]:
    rows = _list_paginated(f"repos/{repo_slug}/labels?per_page=100")
    labels: list[str] = []
    for row in rows:
        name = row.get("name")
        if isinstance(name, str) and name.strip():
            labels.append(name.strip())
    return sorted(set(labels), key=str.lower)


def _load_reference_text() -> str:
    paths = [Path("docs/LABELS.md"), *sorted(Path(".github/workflows").glob("*.yml"))]
    chunks: list[str] = []
    for path in paths:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8").lower())
    return "\n".join(chunks)


def _open_label_usage(repo_slug: str) -> dict[str, tuple[int, int]]:
    rows = _list_paginated(f"repos/{repo_slug}/issues?state=open&per_page=100")
    usage: dict[str, tuple[int, int]] = {}
    for row in rows:
        labels_raw = row.get("labels")
        if not isinstance(labels_raw, list):
            continue
        is_pr = isinstance(row.get("pull_request"), dict)
        for item in labels_raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            key = name.strip()
            issues, prs = usage.get(key, (0, 0))
            if is_pr:
                usage[key] = (issues, prs + 1)
            else:
                usage[key] = (issues + 1, prs)
    return usage


def _is_protected_label(name: str) -> bool:
    lower = name.lower()
    return any(lower.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _candidate_milestone_label(name: str) -> bool:
    return bool(MILESTONE_LABEL_RE.fullmatch(name.strip()))


def _delete_label(repo_slug: str, name: str) -> None:
    encoded = quote(name, safe="")
    _gh_api_json(f"repos/{repo_slug}/labels/{encoded}", method="DELETE")


def _write_report(path: Path, *, repo_slug: str, mode: str, decisions: list[LabelDecision]) -> None:
    kept = [d for d in decisions if d.action != "delete"]
    deleted = [d for d in decisions if d.action == "delete"]
    lines: list[str] = []
    lines.append("# Label Cleanup Report")
    lines.append("")
    lines.append(f"- repo: `{repo_slug}`")
    lines.append(f"- mode: `{mode}`")
    lines.append(f"- milestone-like labels scanned: `{len(decisions)}`")
    lines.append(f"- labels deleted/planned-delete: `{len(deleted)}`")
    lines.append(f"- labels kept: `{len(kept)}`")
    lines.append("")
    lines.append("## Delete")
    if not deleted:
        lines.append("- (none)")
    else:
        for item in sorted(deleted, key=lambda d: d.name.lower()):
            lines.append(f"- `{item.name}` ({item.reason})")
    lines.append("")
    lines.append("## Keep")
    if not kept:
        lines.append("- (none)")
    else:
        for item in sorted(kept, key=lambda d: d.name.lower()):
            lines.append(
                f"- `{item.name}` ({item.reason}; open_issues={item.open_issue_count}; open_prs={item.open_pr_count})"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete unused milestone-like labels safely.")
    parser.add_argument("--repo", default=None, help="GitHub repository slug (<owner>/<repo>).")
    parser.add_argument("--apply", action="store_true", help="Apply deletions. Default is dry-run.")
    parser.add_argument("--report", default=None, help="Optional markdown report path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "apply" if args.apply else "dry-run"
    report_path = Path(args.report) if args.report else None
    try:
        repo_slug = _resolve_repo_slug(args.repo)
        labels = _list_labels(repo_slug)
        reference_text = _load_reference_text()
        open_usage = _open_label_usage(repo_slug)

        decisions: list[LabelDecision] = []
        for label in labels:
            if not _candidate_milestone_label(label):
                continue
            if _is_protected_label(label):
                decisions.append(
                    LabelDecision(
                        name=label,
                        reason="protected-prefix",
                        open_issue_count=0,
                        open_pr_count=0,
                        action="keep",
                    )
                )
                continue
            if label.lower() in reference_text:
                decisions.append(
                    LabelDecision(
                        name=label,
                        reason="referenced-in-docs-or-workflows",
                        open_issue_count=0,
                        open_pr_count=0,
                        action="keep",
                    )
                )
                continue

            open_issue_count, open_pr_count = open_usage.get(label, (0, 0))
            if open_issue_count > 0 or open_pr_count > 0:
                decisions.append(
                    LabelDecision(
                        name=label,
                        reason="still-in-use",
                        open_issue_count=open_issue_count,
                        open_pr_count=open_pr_count,
                        action="keep",
                    )
                )
                continue

            if args.apply:
                _delete_label(repo_slug, label)
            decisions.append(
                LabelDecision(
                    name=label,
                    reason="unused-milestone-label",
                    open_issue_count=0,
                    open_pr_count=0,
                    action="delete",
                )
            )

        print("LABEL_CLEANUP_SUMMARY")
        print(f"mode: {mode}")
        print(f"repo: {repo_slug}")
        print(f"scanned_candidates: {len(decisions)}")
        print(f"delete_count: {sum(1 for d in decisions if d.action == 'delete')}")
        print(f"keep_count: {sum(1 for d in decisions if d.action != 'delete')}")
        for decision in sorted(decisions, key=lambda d: d.name.lower()):
            print(
                f"label={decision.name} action={decision.action} reason={decision.reason} "
                f"open_issues={decision.open_issue_count} open_prs={decision.open_pr_count}"
            )

        if report_path is not None:
            _write_report(report_path, repo_slug=repo_slug, mode=mode, decisions=decisions)
            print(f"report: {report_path}")
        print("LABEL_CLEANUP_OK")
        return 0
    except LabelCleanupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
