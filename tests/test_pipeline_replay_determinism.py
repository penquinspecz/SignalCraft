"""
Real pipeline replay determinism test.

Phase2-C12: Runs the actual pipeline twice in SNAPSHOT mode with identical inputs
and verifies byte-identical outputs. This replaces the synthetic replay check.

This test is intentionally heavier than unit tests - it exercises the full pipeline
to prove deterministic behavior end-to-end.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def snapshot_env() -> dict[str, str]:
    """Environment variables for deterministic snapshot-mode pipeline execution."""
    env = os.environ.copy()
    env.update(
        {
            "CAREERS_MODE": "SNAPSHOT",
            "EMBED_PROVIDER": "stub",
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "LC_ALL": "C.UTF-8",
            "DISCORD_WEBHOOK_URL": "",
        }
    )
    return env


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_fixture_data_dir(work_dir: Path) -> tuple[Path, Path]:
    source_snapshot = REPO_ROOT / "data" / "openai_snapshots" / "index.html"
    source_profile = REPO_ROOT / "data" / "candidate_profile.json"
    if not source_snapshot.exists():
        raise FileNotFoundError(f"missing pinned snapshot fixture: {source_snapshot}")
    if not source_profile.exists():
        raise FileNotFoundError(f"missing pinned candidate fixture: {source_profile}")

    data_dir = work_dir / "data"
    snapshot_dir = data_dir / "openai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_snapshot, snapshot_dir / "index.html")
    shutil.copy2(source_profile, data_dir / "candidate_profile.json")
    return data_dir, source_profile


def _parse_run_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if line.startswith("JOBINTEL_RUN_ID="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    return None


def _find_run_dir(state_dir: Path, run_id: str) -> Path:
    candidates: list[Path] = []
    for report_path in state_dir.rglob("run_report.json"):
        try:
            payload = _load_json(report_path)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            candidates.append(report_path.parent)
    if not candidates:
        raise FileNotFoundError(f"unable to resolve run_dir for run_id={run_id} under {state_dir}")
    candidates.sort()
    return candidates[-1]


def _run_pipeline(work_dir: Path, env: dict[str, str], *, sequence: int) -> Path:
    """Run the pipeline once and return the run directory."""
    data_dir, profile_source = _build_fixture_data_dir(work_dir)
    state_dir = work_dir / "state"
    candidate_input_dir = state_dir / "candidates" / "local" / "inputs"
    candidate_input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(profile_source, candidate_input_dir / "candidate_profile.json")

    run_id = f"2026-02-28T00:00:0{sequence}Z"
    env_copy = env.copy()
    env_copy.update(
        {
            "JOBINTEL_DATA_DIR": str(data_dir),
            "JOBINTEL_STATE_DIR": str(state_dir),
            "JOBINTEL_PROVIDER_ID": "openai",
            "JOBINTEL_RUN_ID": run_id,
            "PYTHONPATH": str(REPO_ROOT / "src"),
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_daily.py"),
            "--no_subprocess",
            "--offline",
            "--snapshot-only",
            "--providers",
            "openai",
            "--profiles",
            "cs",
            "--no_post",
        ],
        cwd=str(REPO_ROOT),
        env=env_copy,
        capture_output=True,
        text=True,
        timeout=150,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(f"Pipeline failed:\nstdout: {result.stdout[-3000:]}\nstderr: {result.stderr[-3000:]}")

    parsed_run_id = _parse_run_id(result.stdout) or run_id
    return _find_run_dir(state_dir, parsed_run_id)


@pytest.mark.slow
class TestPipelineReplayDeterminism:
    """Run the pipeline twice and verify byte-identical outputs."""

    def test_two_runs_produce_identical_artifacts(self, snapshot_env: dict[str, str], tmp_path: Path) -> None:
        """Two pipeline runs with identical inputs must produce identical artifact hashes."""
        run1_dir = _run_pipeline(tmp_path / "run1", snapshot_env, sequence=1)
        run2_dir = _run_pipeline(tmp_path / "run2", snapshot_env, sequence=2)

        compare_script = REPO_ROOT / "scripts" / "compare_run_artifacts.py"
        compare_env = os.environ.copy()
        compare_env["PYTHONPATH"] = str(REPO_ROOT)
        result = subprocess.run(
            [
                sys.executable,
                str(compare_script),
                str(run1_dir),
                str(run2_dir),
                "--allow-run-id-drift",
                "--repo-root",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(REPO_ROOT),
            env=compare_env,
            check=False,
        )

        if result.returncode != 0:
            pytest.fail(
                "Determinism check failed - two runs with identical inputs produced different outputs:\n"
                f"{result.stdout[-3000:]}\n"
                f"{result.stderr[-1000:]}"
            )
