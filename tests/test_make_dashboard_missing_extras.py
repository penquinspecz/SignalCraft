from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


def test_make_dashboard_missing_extras_prints_install_guidance(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    # Use python -S to disable site-packages and deterministically simulate
    # missing FastAPI/Uvicorn without network installs.
    wrapper = tmp_path / "python-noextras.sh"
    wrapper.write_text(f"#!/bin/sh\nexec {sys.executable} -S \"$@\"\n", encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)

    env = os.environ.copy()
    env.setdefault("PYTHONNOUSERSITE", "1")

    result = subprocess.run(
        ["make", "dashboard", f"PY={wrapper}"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    combined = "\n".join((result.stdout, result.stderr))
    assert result.returncode == 2
    assert "Dashboard deps missing (fastapi, uvicorn). Install with: pip install -e '.[dashboard]'" in combined
