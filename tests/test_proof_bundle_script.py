"""Tests for proof bundle and dashboard contract smoke scripts."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_dashboard_contract_smoke_fails_when_unreachable() -> None:
    """dashboard_contract_smoke.sh exits non-zero when dashboard is not reachable."""
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "dev" / "dashboard_contract_smoke.sh"
    assert script.exists(), f"Script not found: {script}"
    result = subprocess.run(
        ["bash", str(script), "http://127.0.0.1:19999"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected non-zero exit when dashboard unreachable"
    assert "not reachable" in result.stderr or "FAIL" in result.stderr
