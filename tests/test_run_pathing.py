from __future__ import annotations

from pathlib import Path

import pytest

from ji_engine.pipeline.run_pathing import resolve_summary_path, sanitize_run_id, summary_path_text


def test_sanitize_run_id_normalizes_timestamp_separators() -> None:
    assert sanitize_run_id("2026-02-18T03:15:40.123Z") == "20260218T031540123Z"


def test_sanitize_run_id_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="Unsafe run_id"):
        sanitize_run_id("../../etc/passwd")


def test_sanitize_run_id_rejects_slash() -> None:
    with pytest.raises(ValueError, match="Unsafe run_id"):
        sanitize_run_id("2026/01/01T000000Z")


def test_sanitize_run_id_rejects_backslash() -> None:
    with pytest.raises(ValueError, match="Unsafe run_id"):
        sanitize_run_id(r"2026\01\01T000000Z")


def test_sanitize_run_id_rejects_empty() -> None:
    with pytest.raises(ValueError, match="Invalid run_id"):
        sanitize_run_id("")


def test_sanitize_run_id_rejects_none() -> None:
    with pytest.raises(ValueError, match="Invalid run_id"):
        sanitize_run_id(None)  # type: ignore[arg-type]


def test_sanitize_run_id_normal_timestamp() -> None:
    assert sanitize_run_id("2026-02-18T03:15:40.123Z") == "20260218T031540123Z"


def test_sanitize_run_id_normalizes_utc_offset_suffix() -> None:
    assert sanitize_run_id("2026-01-01T00:00:00+00:00") == "20260101T000000Z"


def test_sanitize_run_id_already_clean() -> None:
    assert sanitize_run_id("20260218T031540123Z") == "20260218T031540123Z"


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


def test_resolve_run_path_stays_within_base(tmp_path: Path) -> None:
    from ji_engine.pipeline.run_pathing import resolve_run_path

    result = resolve_run_path(tmp_path, "20260218T031540123Z")
    assert result == tmp_path / "20260218T031540123Z"


def test_resolve_run_path_rejects_traversal(tmp_path: Path) -> None:
    from ji_engine.pipeline.run_pathing import resolve_run_path

    with pytest.raises(ValueError, match="Unsafe run_id"):
        resolve_run_path(tmp_path, "../../etc")
