from __future__ import annotations

from pathlib import Path

from ji_engine.pipeline.run_pathing import resolve_summary_path, sanitize_run_id, summary_path_text


def test_sanitize_run_id_normalizes_timestamp_separators() -> None:
    assert sanitize_run_id("2026-02-18T03:15:40.123Z") == "20260218T031540123Z"


def test_summary_path_text_prefers_repo_relative(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    run_path = repo_root / "state" / "runs" / "20260218T031540Z" / "run_summary.v1.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text("{}", encoding="utf-8")

    assert summary_path_text(run_path, repo_root=repo_root) == "state/runs/20260218T031540Z/run_summary.v1.json"


def test_resolve_summary_path_supports_absolute_and_repo_relative(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    relative = "state/runs/20260218T031540Z/run_summary.v1.json"
    absolute = (repo_root / relative).resolve()

    assert resolve_summary_path(relative, repo_root=repo_root) == absolute
    assert resolve_summary_path(str(absolute), repo_root=repo_root) == absolute
