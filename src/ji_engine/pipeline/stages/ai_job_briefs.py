"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from pathlib import Path


def build_ai_job_briefs_command(
    *,
    python_executable: str,
    repo_root: Path,
    provider: str,
    profile: str,
    ranked_path: Path,
    run_id: str,
    max_jobs: str,
    max_tokens_per_job: str,
    total_budget: str,
) -> list[str]:
    return [
        python_executable,
        str(repo_root / "scripts" / "run_ai_job_briefs.py"),
        "--provider",
        provider,
        "--profile",
        profile,
        "--ranked_path",
        str(ranked_path),
        "--run_id",
        run_id,
        "--max_jobs",
        max_jobs,
        "--max_tokens_per_job",
        max_tokens_per_job,
        "--total_budget",
        total_budget,
    ]
