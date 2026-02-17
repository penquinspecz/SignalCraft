#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Iterable, Sequence, Set, Tuple

CHANGELOG_PATH = "CHANGELOG.md"
VERSION_FILES = ("pyproject.toml",)
RELEASE_LABEL = "release"
RELEASE_PROCESS_DOC = "docs/RELEASE_PROCESS.md"


def _run_git(args: Sequence[str]) -> str:
    cp = subprocess.run(["git", *args], check=True, text=True, capture_output=True)
    return cp.stdout.strip()


def _normalize_files(files: Iterable[str]) -> Set[str]:
    out: Set[str] = set()
    for file_name in files:
        candidate = file_name.strip()
        if candidate:
            out.add(candidate)
    return out


def _labels_from_event(event_path: Path | None) -> Set[str]:
    if event_path is None or not event_path.exists():
        return set()
    payload = json.loads(event_path.read_text(encoding="utf-8"))
    pull_request = payload.get("pull_request") if isinstance(payload, dict) else None
    labels = pull_request.get("labels") if isinstance(pull_request, dict) else None
    if not isinstance(labels, list):
        return set()
    out: Set[str] = set()
    for label in labels:
        name = label.get("name") if isinstance(label, dict) else None
        if isinstance(name, str) and name.strip():
            out.add(name.strip().lower())
    return out


def _changed_files(base_ref: str, head_ref: str) -> Set[str]:
    if not base_ref.strip():
        raise RuntimeError("base ref is required to compute changed files")
    merge_base = _run_git(["merge-base", base_ref, head_ref])
    changed = _run_git(["diff", "--name-only", f"{merge_base}..{head_ref}"])
    return _normalize_files(changed.splitlines())


def evaluate_policy(changed_files: Set[str], labels: Set[str]) -> Tuple[bool, str]:
    reasons = []
    if RELEASE_LABEL in labels:
        reasons.append(f'PR has "{RELEASE_LABEL}" label')
    if any(version_file in changed_files for version_file in VERSION_FILES):
        reasons.append("version file changed (pyproject.toml)")

    if not reasons:
        return True, "skip: policy not triggered"
    if CHANGELOG_PATH in changed_files:
        return True, "pass: changelog updated"

    reason_text = "; ".join(reasons)
    message = (
        "ERROR: changelog policy check failed.\n"
        f"Reason: {reason_text}\n"
        f"Required fix: update {CHANGELOG_PATH} in this PR.\n"
        f"Release process: {RELEASE_PROCESS_DOC}\n"
    )
    return False, message


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enforce lightweight release changelog policy.")
    parser.add_argument("--base-ref", default=os.environ.get("GITHUB_BASE_REF", ""))
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH", ""))
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--label", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    labels = {label.strip().lower() for label in args.label if label.strip()}

    event_path = Path(args.event_path) if args.event_path else None
    labels |= _labels_from_event(event_path)

    if args.changed_file:
        changed_files = _normalize_files(args.changed_file)
    else:
        if not args.base_ref:
            print("changelog policy: skip (no base ref and no explicit changed files)")
            return 0
        changed_files = _changed_files(args.base_ref, args.head_ref)

    ok, message = evaluate_policy(changed_files, labels)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
