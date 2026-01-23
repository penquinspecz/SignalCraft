import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_shell_scripts_syntax() -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "scripts"
    script_paths = sorted(p for p in scripts_dir.glob("*.sh") if p.is_file())
    assert script_paths, "no shell scripts found"
    for path in script_paths:
        result = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, f"bash -n failed for {path}: {result.stderr}"


@pytest.mark.parametrize(
    "script_name",
    [
        "run_ecs_once.sh",
        "verify_ops.sh",
        "ecs_verify_task.sh",
        "verify_s3_pointers.sh",
        "show_run_provenance.sh",
    ],
)
def test_shell_script_smoke_no_unbound(script_name: str) -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / script_name
    env = {"PATH": os.environ.get("PATH", "")}
    result = subprocess.run([bash, str(script)], capture_output=True, text=True, env=env)
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "unbound variable" not in combined
    assert "bad substitution" not in combined
