"""
M13: No run filesystem scan outside RunRepository.

Runtime code (src/, scripts/) must not call Path.iterdir/glob/rglob on RUN_METADATA_DIR
or run subdirs. RunRepository is the only allowed scanner. This test monkeypatches
Path.iterdir and Path.glob to raise when invoked on run metadata paths by non-RunRepository code.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any


def _is_run_repository_caller() -> bool:
    for frame in inspect.stack():
        try:
            fname = frame.filename
        except Exception:
            continue
        if "run_repository" in fname and "test_" not in fname:
            return True
    return False


def test_runner_resolve_latest_uses_repository_not_iterdir(tmp_path: Path, monkeypatch: Any) -> None:
    """_resolve_latest_run_ranked_legacy_scan uses list_run_dirs, not run_root.iterdir()."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    run_root = tmp_path / "state" / "runs"
    run_root.mkdir(parents=True, exist_ok=True)

    import ji_engine.config as config_mod
    import ji_engine.pipeline.runner as runner

    config_mod = importlib.reload(config_mod)
    runner = importlib.reload(runner)

    run_metadata_resolved = config_mod.RUN_METADATA_DIR.resolve()
    original_iterdir = Path.iterdir

    def _patched_iterdir(self: Path) -> Any:
        if _is_run_repository_caller():
            return original_iterdir(self)
        try:
            resolved = self.resolve()
        except OSError:
            return original_iterdir(self)
        if run_metadata_resolved in resolved.parents or resolved == run_metadata_resolved:
            raise AssertionError("Path.iterdir forbidden on run dir outside RunRepository: use list_run_dirs")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _patched_iterdir)

    # Exercise: _resolve_latest_run_ranked_legacy_scan (called when list_runs returns empty)
    # Should not raise because it now uses list_run_dirs (which is in run_repository)
    result = runner._resolve_latest_run_ranked_legacy_scan(
        provider="openai", profile="cs", current_run_id="2026-01-01T00:00:00Z"
    )
    assert result is None  # No runs exist


def test_semantic_finalize_uses_provider_pairs_not_glob(tmp_path: Path, monkeypatch: Any) -> None:
    """finalize_semantic_artifacts with provider_profile_pairs does not glob semantic_dir."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    run_dir = tmp_path / "state" / "runs" / "20260101T000000Z"
    semantic_dir = run_dir / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    (semantic_dir / "scores_openai_cs.json").write_text(
        '{"entries":[],"cache_hit_counts":{}}',
        encoding="utf-8",
    )

    import ji_engine.config as config_mod
    import ji_engine.semantic.step as semantic_step

    config_mod = importlib.reload(config_mod)
    semantic_step = importlib.reload(semantic_step)

    run_metadata_resolved = config_mod.RUN_METADATA_DIR.resolve()
    original_glob = Path.glob

    def _patched_glob(self: Path, pattern: str) -> Any:
        if _is_run_repository_caller():
            return original_glob(self, pattern)
        try:
            resolved = self.resolve()
        except OSError:
            return original_glob(self, pattern)
        if run_metadata_resolved in resolved.parents or resolved == run_metadata_resolved:
            raise AssertionError("Path.glob forbidden on run dir outside RunRepository: use provider_profile_pairs")
        return original_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", _patched_glob)

    summary, summary_path, scores_path = semantic_step.finalize_semantic_artifacts(
        run_id="2026-01-01T00:00:00Z",
        run_metadata_dir=tmp_path / "state" / "runs",
        enabled=True,
        model_id="test",
        policy={"max_jobs": 200, "top_k": 50, "max_boost": 5.0, "min_similarity": 0.72},
        provider_profile_pairs=[("openai", "cs")],
    )
    assert summary["enabled"] is True
    assert summary_path.exists()


def test_prune_state_uses_run_repository_helper(tmp_path: Path, monkeypatch: Any) -> None:
    """plan_prune uses list_run_metadata_paths_from_dir, not runs_dir.glob."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    runs_dir = tmp_path / "state" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "20260101T000000Z.json").write_text("{}", encoding="utf-8")
    (tmp_path / "state" / "history").mkdir(parents=True, exist_ok=True)

    import ji_engine.config as config_mod
    from scripts import prune_state

    config_mod = importlib.reload(config_mod)
    prune_state = importlib.reload(prune_state)  # noqa: F811

    run_metadata_resolved = config_mod.RUN_METADATA_DIR.resolve()
    original_glob = Path.glob

    def _patched_glob(self: Path, pattern: str) -> Any:
        if _is_run_repository_caller():
            return original_glob(self, pattern)
        try:
            resolved = self.resolve()
        except OSError:
            return original_glob(self, pattern)
        if run_metadata_resolved in resolved.parents or resolved == run_metadata_resolved:
            raise AssertionError(
                "Path.glob forbidden on runs dir outside RunRepository: use list_run_metadata_paths_from_dir"
            )
        return original_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", _patched_glob)

    actions = prune_state.plan_prune(
        state_dir=tmp_path / "state",
        runs_dir=runs_dir,
        history_dir=tmp_path / "state" / "history",
        keep_run_reports=1,
        keep_history_per_profile=1,
    )
    # Should not raise; may or may not have prune actions
    assert isinstance(actions, list)
