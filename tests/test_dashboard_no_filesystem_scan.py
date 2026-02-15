"""
Dashboard no-filesystem-scan enforcement: common read paths use RunRepository/index-backed resolution.

We monkeypatch Path.glob to raise when invoked on run metadata dir or run subdirs;
if the dashboard uses index-backed resolution (artifacts, providers), it never calls glob
and the test passes.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def _sanitize(run_id: str) -> str:
    return run_id.replace(":", "").replace("-", "").replace(".", "")


def test_dashboard_run_detail_and_semantic_summary_use_index_not_glob(tmp_path: Path, monkeypatch: Any) -> None:
    """run_detail and run_semantic_summary must use index-backed resolution; run_dir.glob would raise."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    config = importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-02-15T12:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    semantic_dir = run_dir / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)

    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "providers": {"openai": {"profiles": {"cs": {}}}},
        "artifacts": {"ai_insights.cs.json": "ai_insights.cs.json"},
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (run_dir / "ai_insights.cs.json").write_text(
        json.dumps({"metadata": {"prompt_version": "weekly_insights_v3"}}),
        encoding="utf-8",
    )
    (run_dir / "run_report.json").write_text(
        json.dumps({"semantic_enabled": True, "semantic_mode": "boost"}),
        encoding="utf-8",
    )
    (run_dir / "costs.json").write_text(json.dumps({"total_estimated_tokens": 0}), encoding="utf-8")
    (semantic_dir / "semantic_summary.json").write_text(
        json.dumps({"enabled": True, "model_id": "v1"}),
        encoding="utf-8",
    )
    (semantic_dir / "scores_openai_cs.json").write_text(
        json.dumps({"entries": [{"provider": "openai", "profile": "cs", "job_id": "j1"}]}),
        encoding="utf-8",
    )

    dashboard.RUN_REPOSITORY.rebuild_index(candidate_id="local")

    run_metadata_resolved = config.RUN_METADATA_DIR.resolve()
    original_glob = Path.glob

    def _patched_glob(self: Path, pattern: str) -> Any:
        try:
            resolved = self.resolve()
        except OSError:
            return original_glob(self, pattern)
        if run_metadata_resolved in resolved.parents or resolved == run_metadata_resolved:
            raise AssertionError("Direct glob forbidden on run dir: use RunRepository/index-backed resolution")
        return original_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", _patched_glob)

    client = TestClient(dashboard.app)
    detail = client.get(f"/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["ai_prompt_version"] == "weekly_insights_v3"

    semantic = client.get(f"/runs/{run_id}/semantic_summary/cs")
    assert semantic.status_code == 200
    assert semantic.json()["entries"] == [{"provider": "openai", "profile": "cs", "job_id": "j1"}]
