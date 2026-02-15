"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from pathlib import Path


def build_score_command(
    *,
    python_executable: str,
    repo_root: Path,
    profile: str,
    provider: str,
    in_path: Path,
    scoring_config_path: Path,
    out_json: Path,
    out_csv: Path,
    out_families: Path,
    out_md: Path,
    min_score: int,
    out_md_top_n: Path,
    semantic_scores_out: Path,
    us_only: bool,
    prefer_ai: bool,
) -> list[str]:
    cmd = [
        python_executable,
        str(repo_root / "scripts" / "score_jobs.py"),
        "--profile",
        profile,
        "--provider_id",
        provider,
        "--in_path",
        str(in_path),
        "--scoring_config",
        str(scoring_config_path),
        "--out_json",
        str(out_json),
        "--out_csv",
        str(out_csv),
        "--out_families",
        str(out_families),
        "--out_md",
        str(out_md),
        "--min_score",
        str(min_score),
        "--out_md_top_n",
        str(out_md_top_n),
        "--semantic_scores_out",
        str(semantic_scores_out),
    ]
    if us_only:
        cmd.append("--us_only")
    if prefer_ai:
        cmd.append("--prefer_ai")
    return cmd
