#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

EXPECTED_AWS_TEST_DEFAULTS = {
    "AWS_EC2_METADATA_DISABLED": "true",
    "AWS_CONFIG_FILE": "/dev/null",
    "AWS_SHARED_CREDENTIALS_FILE": "/dev/null",
}

REQUIRED_DETERMINISM_DOCS = (
    "docs/DETERMINISM_CONTRACT.md",
    "docs/RUN_REPORT.md",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    level: str  # PASS | WARN | FAIL
    detail: str


def _run(cmd: Sequence[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )


def _check_git_status(repo_root: Path) -> CheckResult:
    cp = _run(("git", "status", "--porcelain=v1"), repo_root)
    if cp.returncode != 0:
        return CheckResult("git_status", "FAIL", cp.stderr.strip() or "git status failed")
    if cp.stdout.strip():
        return CheckResult(
            "git_status",
            "WARN",
            "worktree is dirty; commit/stash before merge/release operations",
        )
    return CheckResult("git_status", "PASS", "worktree is clean")


def _parse_worktrees(raw: str) -> List[dict]:
    entries: List[dict] = []
    current: dict = {}
    for line in raw.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if " " not in line:
            continue
        key, value = line.split(" ", 1)
        current[key] = value.strip()
    if current:
        entries.append(current)
    return entries


def _check_worktrees(repo_root: Path) -> CheckResult:
    cp = _run(("git", "worktree", "list", "--porcelain"), repo_root)
    if cp.returncode != 0:
        return CheckResult("worktrees", "FAIL", cp.stderr.strip() or "git worktree list failed")
    cwd = str(repo_root.resolve())
    unexpected_main_holders: List[str] = []
    for entry in _parse_worktrees(cp.stdout):
        path = entry.get("worktree")
        branch = entry.get("branch", "")
        if not path:
            continue
        if branch.endswith("/main") and str(Path(path).resolve()) != cwd:
            unexpected_main_holders.append(path)
    if unexpected_main_holders:
        joined = ", ".join(sorted(unexpected_main_holders))
        return CheckResult(
            "worktrees",
            "FAIL",
            f"main is checked out in additional worktree(s): {joined}",
        )
    return CheckResult("worktrees", "PASS", "no unexpected worktree holds main")


def _check_venv(repo_root: Path) -> CheckResult:
    venv_python = repo_root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return CheckResult("venv", "FAIL", "missing .venv/bin/python")
    cp = _run((str(venv_python), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"), repo_root)
    if cp.returncode != 0:
        return CheckResult("venv", "FAIL", "unable to execute .venv/bin/python")
    version = cp.stdout.strip()
    if version != "3.12":
        return CheckResult("venv", "WARN", f"expected Python 3.12 in .venv, found {version}")
    return CheckResult("venv", "PASS", f".venv python version is {version}")


def _check_offline_test_defaults(repo_root: Path) -> CheckResult:
    conftest = repo_root / "tests" / "conftest.py"
    if not conftest.exists():
        return CheckResult("offline_test_env", "FAIL", "tests/conftest.py missing")
    content = conftest.read_text(encoding="utf-8")
    missing = [k for k, v in EXPECTED_AWS_TEST_DEFAULTS.items() if f'"{k}": "{v}"' not in content]
    if missing:
        return CheckResult(
            "offline_test_env",
            "FAIL",
            f"tests/conftest.py missing default(s): {', '.join(missing)}",
        )
    if "os.environ.setdefault(" not in content:
        return CheckResult(
            "offline_test_env",
            "FAIL",
            "tests/conftest.py does not set offline-safe env defaults",
        )
    runtime_missing = [k for k in EXPECTED_AWS_TEST_DEFAULTS if os.environ.get(k) != EXPECTED_AWS_TEST_DEFAULTS[k]]
    if runtime_missing:
        return CheckResult(
            "offline_test_env",
            "WARN",
            "shell env differs from test defaults; pytest harness still enforces defaults",
        )
    return CheckResult("offline_test_env", "PASS", "offline-safe AWS test defaults present")


def _check_determinism_docs(repo_root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_DETERMINISM_DOCS if not (repo_root / path).exists()]
    if missing:
        return CheckResult(
            "determinism_docs",
            "FAIL",
            f"missing required determinism docs: {', '.join(missing)}",
        )
    return CheckResult("determinism_docs", "PASS", "determinism contract docs are present")


def _format_result(result: CheckResult) -> str:
    return f"[{result.level}] {result.name}: {result.detail}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Local repository guardrails (fast, offline-safe).")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    results = [
        _check_git_status(repo_root),
        _check_worktrees(repo_root),
        _check_venv(repo_root),
        _check_offline_test_defaults(repo_root),
        _check_determinism_docs(repo_root),
    ]

    if args.json:
        print(
            json.dumps(
                [{"name": r.name, "level": r.level, "detail": r.detail} for r in results],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("SignalCraft repo doctor")
        for result in results:
            print(_format_result(result))

    fail_count = sum(1 for r in results if r.level == "FAIL")
    if fail_count:
        print(f"doctor: {fail_count} failing check(s)")
        return 2
    warn_count = sum(1 for r in results if r.level == "WARN")
    if warn_count:
        print(f"doctor: completed with {warn_count} warning(s)")
    else:
        print("doctor: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
