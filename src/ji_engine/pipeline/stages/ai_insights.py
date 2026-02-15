"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from pathlib import Path


def build_ai_insights_command(
    *,
    python_executable: str,
    repo_root: Path,
    provider: str,
    profile: str,
    ranked_path: Path,
    run_id: str,
    prev_path: Path | None,
) -> list[str]:
    cmd = [
        python_executable,
        str(repo_root / "scripts" / "run_ai_insights.py"),
        "--provider",
        provider,
        "--profile",
        profile,
        "--ranked_path",
        str(ranked_path),
        "--run_id",
        run_id,
    ]
    if prev_path is not None:
        cmd.extend(["--prev_path", str(prev_path)])
    return cmd
