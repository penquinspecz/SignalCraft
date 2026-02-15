"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from pathlib import Path


def build_classify_command(*, python_executable: str, repo_root: Path, in_path: Path, out_path: Path) -> list[str]:
    return [
        python_executable,
        str(repo_root / "scripts" / "run_classify.py"),
        "--in_path",
        str(in_path),
        "--out_path",
        str(out_path),
    ]
