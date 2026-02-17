from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any


def _reload_modules(tmp_path: Path, monkeypatch: Any):
    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    import ji_engine.config as config
    import ji_engine.pipeline.runner as runner

    config = importlib.reload(config)
    runner = importlib.reload(runner)
    return config, runner


def _write_ranked(runner: Any, run_id: str, provider: str, profile: str) -> Path:
    run_dir = runner._run_registry_dir(run_id)
    path = run_dir / provider / profile / f"{provider}_ranked_jobs.{profile}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    (run_dir / "run_report.json").write_text("{}", encoding="utf-8")
    (run_dir / "index.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": run_id}),
        encoding="utf-8",
    )
    return path


def _legacy_scan_expected(runner: Any, provider: str, profile: str, current_run_id: str) -> Path | None:
    run_root = (
        runner.RUN_METADATA_DIR
        if runner.CANDIDATE_ID == runner.DEFAULT_CANDIDATE_ID
        else runner.candidate_run_metadata_dir(runner.CANDIDATE_ID)
    )
    if not run_root.exists():
        return None
    current_name = runner._sanitize_run_id(current_run_id)
    candidates: list[tuple[float, str, Path]] = []
    for run_dir in run_root.iterdir():
        if not run_dir.is_dir() or run_dir.name == current_name:
            continue
        ranked = run_dir / provider / profile / f"{provider}_ranked_jobs.{profile}.json"
        if not ranked.exists():
            continue
        report = run_dir / "run_report.json"
        mtime = report.stat().st_mtime if report.exists() else run_dir.stat().st_mtime
        candidates.append((mtime, run_dir.name, ranked))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[-1][2]


def test_latest_run_ranked_matches_legacy_fixture(tmp_path: Path, monkeypatch: Any) -> None:
    _, runner = _reload_modules(tmp_path, monkeypatch)

    provider = "openai"
    profile = "cs"
    current_run_id = "2026-02-15T10:00:00Z"
    older_run = "2026-02-15T09:00:00Z"
    latest_run = "2026-02-15T09:30:00Z"

    _write_ranked(runner, older_run, provider, profile)
    _write_ranked(runner, latest_run, provider, profile)
    _write_ranked(runner, current_run_id, provider, profile)

    expected = _legacy_scan_expected(runner, provider, profile, current_run_id)
    actual = runner._resolve_latest_run_ranked(provider, profile, current_run_id)
    assert actual == expected


def test_latest_run_ranked_uses_deterministic_index_order(tmp_path: Path, monkeypatch: Any) -> None:
    _, runner = _reload_modules(tmp_path, monkeypatch)

    provider = "openai"
    profile = "cs"
    current_run_id = "2026-02-15T10:00:00Z"
    run_a = "2026-02-15T09:00:00Za"
    run_b = "2026-02-15T09:00:00Zb"

    path_a = _write_ranked(runner, run_a, provider, profile)
    path_b = _write_ranked(runner, run_b, provider, profile)
    _write_ranked(runner, current_run_id, provider, profile)

    # RunRepository orders by (timestamp DESC, run_id DESC); run_b > run_a, so run_b preferred.
    monkeypatch.setattr(
        runner,
        "_resolve_latest_run_ranked_legacy_scan",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("legacy scan should not be used")),
    )

    assert runner._resolve_latest_run_ranked(provider, profile, current_run_id) == path_b
    assert runner._resolve_latest_run_ranked(provider, profile, current_run_id) != path_a
