"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


def build_scrape_command(
    *,
    python_executable: str,
    repo_root: Path,
    scrape_mode: str,
    providers: Sequence[str],
    providers_config: str,
    snapshot_only: bool,
    snapshot_write_dir: Path | None,
) -> list[str]:
    cmd = [
        python_executable,
        str(repo_root / "scripts" / "run_scrape.py"),
        "--mode",
        scrape_mode,
        "--providers",
        ",".join(providers),
        "--providers-config",
        providers_config,
    ]
    if snapshot_write_dir is not None:
        cmd.extend(["--snapshot-write-dir", str(snapshot_write_dir)])
    if snapshot_only:
        cmd.append("--snapshot-only")
    return cmd
