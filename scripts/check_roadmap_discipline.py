#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ji_engine.roadmap_discipline import (  # noqa: E402
    ROADMAP_PATH,
    SHA_RE,
    evaluate_roadmap_guard,
    parse_last_verified_stamp,
)


def _run_git(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(["git", *args], check=False, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        return result.returncode, (result.stderr or result.stdout).strip()
    return 0, result.stdout.strip()


def _load_changed_files(args: argparse.Namespace) -> list[str]:
    if args.changed_file:
        return sorted(set(path.strip() for path in args.changed_file if path.strip()))
    if args.changed_files_path:
        payload = Path(args.changed_files_path).read_text(encoding="utf-8")
        return sorted(set(line.strip() for line in payload.splitlines() if line.strip()))
    rc, out = _run_git(["diff", "--name-only", "HEAD~1..HEAD"])
    if rc != 0:
        return []
    return sorted(set(line.strip() for line in out.splitlines() if line.strip()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Roadmap discipline guard: verifies Last verified stamp and roadmap updates for sensitive changes."
    )
    parser.add_argument("--roadmap-path", default=ROADMAP_PATH)
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed file path (can be repeated). If omitted, git diff HEAD~1..HEAD is used.",
    )
    parser.add_argument("--changed-files-path", default="", help="Text file containing changed files (one per line).")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings and errors (default is warn-only).")
    parser.add_argument("--stale-commit-threshold", type=int, default=50)
    args = parser.parse_args(argv)

    roadmap_path = (REPO_ROOT / args.roadmap_path).resolve()
    roadmap_text = roadmap_path.read_text(encoding="utf-8")
    stamp = parse_last_verified_stamp(roadmap_text)

    changed_files = _load_changed_files(args)
    rc_head, head_sha = _run_git(["rev-parse", "--short", "HEAD"])
    if rc_head != 0 or not SHA_RE.match(head_sha):
        head_sha = None

    files_since_stamp: list[str] | None = None
    commits_since_stamp: int | None = None
    if stamp and head_sha and stamp.sha != head_sha:
        rc_files, out_files = _run_git(["diff", "--name-only", f"{stamp.sha}..HEAD"])
        if rc_files == 0:
            files_since_stamp = sorted(set(line.strip() for line in out_files.splitlines() if line.strip()))
        rc_count, out_count = _run_git(["rev-list", "--count", f"{stamp.sha}..HEAD"])
        if rc_count == 0:
            try:
                commits_since_stamp = int(out_count)
            except ValueError:
                commits_since_stamp = None

    result = evaluate_roadmap_guard(
        stamp=stamp,
        changed_files=changed_files,
        head_sha=head_sha,
        files_since_stamp=files_since_stamp,
        commits_since_stamp=commits_since_stamp,
        stale_commit_threshold=args.stale_commit_threshold,
    )

    if not result.findings:
        print("ROADMAP_GUARD status=ok findings=0")
        return 0

    for finding in result.findings:
        print(f"ROADMAP_GUARD level={finding.level} code={finding.code} message={finding.message}")
    print(f"ROADMAP_GUARD status=issues findings={len(result.findings)} strict={1 if args.strict else 0}")

    if args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
