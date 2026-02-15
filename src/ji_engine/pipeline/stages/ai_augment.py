"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from pathlib import Path


def build_ai_augment_command(
    *,
    python_executable: str,
    repo_root: Path,
    in_path: Path | None = None,
    out_path: Path | None = None,
) -> list[str]:
    cmd = [python_executable, str(repo_root / "scripts" / "run_ai_augment.py")]
    if in_path is not None and out_path is not None:
        cmd.extend(["--in_path", str(in_path), "--out_path", str(out_path)])
    return cmd
