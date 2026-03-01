"""Ensure no private _sanitize_run_id copies exist in the codebase."""
from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ALLOWED_FILE = REPO_ROOT / "src" / "ji_engine" / "pipeline" / "run_pathing.py"
SKIP_DIR_NAMES = {".claude", ".git", ".venv", "__pycache__"}


def test_no_duplicate_sanitize_run_id() -> None:
    """Only run_pathing.py should define sanitize_run_id."""
    pattern = re.compile(r"def\s+_?sanitize_run_id")
    violations = []

    for py_file in REPO_ROOT.rglob("*.py"):
        if py_file == ALLOWED_FILE:
            continue
        if any(part in SKIP_DIR_NAMES for part in py_file.parts):
            continue
        if py_file.is_relative_to(REPO_ROOT / "tests") or py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8", errors="replace")
        if pattern.search(text):
            violations.append(str(py_file.relative_to(REPO_ROOT)))

    if violations:
        pytest.fail(
            f"Found duplicate sanitize_run_id definitions "
            f"(should only be in run_pathing.py):\n"
            + "\n".join(f"  - {v}" for v in sorted(violations))
        )
