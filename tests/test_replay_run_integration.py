from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path

import scripts.replay_run as replay_run


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_replay_run_integration_snapshot(tmp_path: Path, monkeypatch, capsys) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    tmp_data = tmp_path / "data"
    tmp_state = tmp_path / "state"
    tmp_data.mkdir(parents=True, exist_ok=True)
    tmp_state.mkdir(parents=True, exist_ok=True)

    for provider in ("openai_snapshots", "anthropic_snapshots"):
        src = repo_root / "data" / provider
        if src.exists():
            shutil.copytree(src, tmp_data / provider)
    candidate_profile = repo_root / "data" / "candidate_profile.json"
    if candidate_profile.exists():
        shutil.copy2(candidate_profile, tmp_data / candidate_profile.name)

    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(tmp_data))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_state))

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    importlib.reload(config)
    importlib.reload(run_daily)

    fixed_run_id = "2026-01-01T00:00:00+00:00"
    monkeypatch.setattr(run_daily, "_utcnow_iso", lambda: fixed_run_id)

    argv = [
        "run_daily.py",
        "--offline",
        "--no_post",
        "--providers",
        "openai",
        "--profiles",
        "cs",
        "--no_subprocess",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert run_daily.main() == 0

    run_dir = run_daily.RUN_METADATA_DIR / run_daily._sanitize_run_id(fixed_run_id)
    report_path = run_dir / "run_report.json"
    assert report_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    verifiable = report.get("verifiable_artifacts")
    assert isinstance(verifiable, dict)
    assert verifiable

    for logical_key, meta in verifiable.items():
        assert isinstance(meta, dict)
        rel_path = Path(meta["path"])
        artifact_path = run_dir / rel_path
        assert artifact_path.exists(), f"missing {logical_key} at {artifact_path}"
        assert _sha256(artifact_path) == meta["sha256"]

    exit_code = replay_run.main(["--run-dir", str(run_dir), "--profile", "cs", "--strict"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS" in out

    # Corrupt one artifact to ensure mismatch reporting is explicit.
    first_key = next(iter(verifiable))
    corrupt_path = run_dir / Path(verifiable[first_key]["path"])
    corrupt_path.write_bytes(b"corrupt")
    exit_code = replay_run.main(["--run-dir", str(run_dir), "--profile", "cs", "--strict"])
    out = capsys.readouterr().out
    assert exit_code == 2
    assert "mismatched" in out.lower()
