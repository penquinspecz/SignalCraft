from __future__ import annotations

import json
from pathlib import Path

import pytest

from ji_engine.run_repository import FileSystemRunRepository


def _safe(run_id: str) -> str:
    return run_id.replace(":", "").replace("-", "").replace(".", "")


def test_resolve_run_dir_prefers_namespaced_local(tmp_path: Path) -> None:
    runs = tmp_path / "state" / "runs"
    repo = FileSystemRunRepository(runs)

    run_id = "2026-02-13T00:00:00Z"
    safe = _safe(run_id)
    namespaced = tmp_path / "state" / "candidates" / "local" / "runs" / safe
    legacy = runs / safe
    namespaced.mkdir(parents=True, exist_ok=True)
    legacy.mkdir(parents=True, exist_ok=True)

    assert repo.resolve_run_dir(run_id, candidate_id="local") == namespaced


def test_resolve_run_dir_local_falls_back_to_legacy(tmp_path: Path) -> None:
    runs = tmp_path / "state" / "runs"
    repo = FileSystemRunRepository(runs)

    run_id = "2026-02-13T00:00:00Z"
    safe = _safe(run_id)
    legacy = runs / safe
    legacy.mkdir(parents=True, exist_ok=True)

    assert repo.resolve_run_dir(run_id, candidate_id="local") == legacy


def test_list_run_dirs_deterministic_and_deduped(tmp_path: Path) -> None:
    runs = tmp_path / "state" / "runs"
    repo = FileSystemRunRepository(runs)

    namespaced_root = tmp_path / "state" / "candidates" / "local" / "runs"
    (namespaced_root / "b").mkdir(parents=True, exist_ok=True)
    (namespaced_root / "a").mkdir(parents=True, exist_ok=True)
    (runs / "a").mkdir(parents=True, exist_ok=True)
    (runs / "c").mkdir(parents=True, exist_ok=True)

    listed = repo.list_run_dirs(candidate_id="local")
    assert [p.name for p in listed] == ["a", "b", "c"]
    assert listed[0] == namespaced_root / "a"


def test_list_run_metadata_paths_deterministic_and_deduped(tmp_path: Path) -> None:
    runs = tmp_path / "state" / "runs"
    repo = FileSystemRunRepository(runs)

    namespaced_root = tmp_path / "state" / "candidates" / "local" / "runs"
    namespaced_root.mkdir(parents=True, exist_ok=True)
    runs.mkdir(parents=True, exist_ok=True)

    (namespaced_root / "a.json").write_text("{}", encoding="utf-8")
    (runs / "a.json").write_text("{}", encoding="utf-8")
    (runs / "b.json").write_text("{}", encoding="utf-8")

    listed = repo.list_run_metadata_paths(candidate_id="local")
    assert [p.name for p in listed] == ["a.json", "b.json"]
    assert listed[0] == namespaced_root / "a.json"


def test_resolve_run_artifact_path_rejects_escape(tmp_path: Path) -> None:
    runs = tmp_path / "state" / "runs"
    repo = FileSystemRunRepository(runs)
    run_id = "2026-02-13T00:00:00Z"

    with pytest.raises(ValueError):
        repo.resolve_run_artifact_path(run_id, "../escape.json", candidate_id="local")


def test_write_run_json_targets_candidate_namespace(tmp_path: Path) -> None:
    runs = tmp_path / "state" / "runs"
    repo = FileSystemRunRepository(runs)
    run_id = "2026-02-13T00:00:00Z"

    out = repo.write_run_json(run_id, "index.json", {"run_id": run_id}, candidate_id="alice")
    assert "/candidates/alice/runs/" in out.as_posix()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
