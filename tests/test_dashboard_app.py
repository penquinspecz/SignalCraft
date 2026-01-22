from __future__ import annotations

import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def _sanitize(run_id: str) -> str:
    return run_id.replace(":", "").replace("-", "").replace(".", "")


def test_dashboard_runs_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import jobintel.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_runs_populated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import jobintel.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "openai_ranked_jobs.cs.json"
    artifact_path.write_text("[]", encoding="utf-8")
    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "providers": {"openai": {"profiles": {"cs": {"diff_counts": {"new": 1, "changed": 0, "removed": 0}}}}},
        "artifacts": {artifact_path.name: artifact_path.relative_to(run_dir).as_posix()},
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() and resp.json()[0]["run_id"] == run_id

    detail = client.get(f"/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id

    artifact = client.get(f"/runs/{run_id}/artifact/{artifact_path.name}")
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("application/json")
