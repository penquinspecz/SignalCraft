"""
M13 enforcement: RunRepository is the ONLY resolver for run discovery.

This test fails if pipeline/scripts use direct directory scan (iterdir/glob)
for run listing instead of RunRepository. We monkeypatch Path.iterdir to raise
when invoked on the run metadata dir; if the code uses RunRepository (index-backed),
it never calls iterdir for run discovery and the test passes.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any


def _sanitize(run_id: str) -> str:
    return run_id.replace(":", "").replace("-", "").replace(".", "")


def test_resolve_latest_run_ranked_uses_run_repository_not_direct_scan(tmp_path: Path, monkeypatch: Any) -> None:
    """_resolve_latest_run_ranked must use RunRepository; direct run_root.iterdir would raise."""
    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import ji_engine.config as config
    import ji_engine.pipeline.runner as runner

    config = importlib.reload(config)
    runner = importlib.reload(runner)

    run_id = "2026-02-15T12:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": run_id}),
        encoding="utf-8",
    )
    (run_dir / "openai" / "cs" / "openai_ranked_jobs.cs.json").parent.mkdir(parents=True, exist_ok=True)
    (run_dir / "openai" / "cs" / "openai_ranked_jobs.cs.json").write_text("[]", encoding="utf-8")
    (run_dir / "run_report.json").write_text("{}", encoding="utf-8")

    runner._run_repository().rebuild_index(candidate_id="local")

    run_metadata_resolved = config.RUN_METADATA_DIR.resolve()
    original_iterdir = Path.iterdir

    def _patched_iterdir(self: Path) -> Any:
        if self.resolve() == run_metadata_resolved:
            raise AssertionError("Direct directory scan forbidden: use RunRepository for run discovery")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _patched_iterdir)

    monkeypatch.setattr(
        runner,
        "_resolve_latest_run_ranked_legacy_scan",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy scan must not be used when index has data")
        ),
    )

    result = runner._resolve_latest_run_ranked("openai", "cs", "2026-02-15T13:00:00Z")
    assert result is not None
    assert _sanitize(run_id) in str(result)
