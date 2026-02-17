from __future__ import annotations

import json
from pathlib import Path


def _sanitize(run_id: str) -> str:
    return run_id.replace(":", "").replace("-", "").replace(".", "")


def _write_index(
    run_dir: Path,
    run_id: str,
    timestamp: str,
    *,
    profiles: list[str] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "run_id": run_id,
        "timestamp": timestamp,
        "artifacts": {},
    }
    if profiles:
        payload["providers"] = {
            "openai": {"profiles": {p: {"artifacts": {}} for p in profiles}},
        }
    (run_dir / "index.json").write_text(json.dumps(payload), encoding="utf-8")


def test_rebuild_index_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    run_a = "2026-01-02T00:00:00Z"
    run_b = "2026-01-03T00:00:00Z"
    _write_index(config.RUN_METADATA_DIR / _sanitize(run_a), run_a, run_a)
    _write_index(config.RUN_METADATA_DIR / _sanitize(run_b), run_b, run_b)

    repo = run_repository.FileSystemRunRepository()
    first = repo.rebuild_index()
    first_list = repo.list_runs()

    second = repo.rebuild_index()
    second_list = repo.list_runs()

    assert first["runs_indexed"] == 2
    assert second["runs_indexed"] == 2
    assert [item["run_id"] for item in first_list] == [item["run_id"] for item in second_list] == [run_b, run_a]


def test_candidate_isolation_same_run_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    run_id = "2026-01-02T00:00:00Z"
    local_run = config.RUN_METADATA_DIR / _sanitize(run_id)
    alice_run = config.candidate_run_metadata_dir("alice") / _sanitize(run_id)

    _write_index(local_run, run_id, "2026-01-02T00:00:00Z")
    _write_index(alice_run, run_id, "2026-01-04T00:00:00Z")

    repo = run_repository.FileSystemRunRepository()
    local_meta = repo.rebuild_index("local")
    alice_meta = repo.rebuild_index("alice")

    assert local_meta["db_path"] != alice_meta["db_path"]
    assert repo.latest_run("local")["timestamp"] == "2026-01-02T00:00:00Z"
    assert repo.latest_run("alice")["timestamp"] == "2026-01-04T00:00:00Z"


def test_latest_run_uses_index_without_filesystem_scan(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    run_id = "2026-01-02T00:00:00Z"
    _write_index(config.RUN_METADATA_DIR / _sanitize(run_id), run_id, run_id)

    repo = run_repository.FileSystemRunRepository()
    repo.rebuild_index("local")

    monkeypatch.setattr(
        repo,
        "_scan_runs_from_filesystem",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("filesystem scan called")),
    )
    latest = repo.latest_run("local")
    assert latest and latest["run_id"] == run_id


def test_corrupt_index_triggers_safe_rebuild(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    run_id = "2026-01-02T00:00:00Z"
    _write_index(config.RUN_METADATA_DIR / _sanitize(run_id), run_id, run_id)

    repo = run_repository.FileSystemRunRepository()
    meta = repo.rebuild_index("local")
    Path(meta["db_path"]).write_text("not a sqlite db", encoding="utf-8")

    runs = repo.list_runs("local")
    assert runs and runs[0]["run_id"] == run_id
    assert Path(meta["db_path"]).read_bytes().startswith(b"SQLite format 3")


def test_list_runs_uses_index_without_filesystem_scan(tmp_path: Path, monkeypatch) -> None:
    """Prove list_runs uses SQLite index when available; no per-run index.json scan."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    run_id = "2026-01-02T00:00:00Z"
    _write_index(config.RUN_METADATA_DIR / _sanitize(run_id), run_id, run_id)

    repo = run_repository.FileSystemRunRepository()
    repo.rebuild_index("local")

    monkeypatch.setattr(
        repo,
        "_scan_runs_from_filesystem",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("filesystem scan called")),
    )
    runs = repo.list_runs("local")
    assert runs and runs[0]["run_id"] == run_id


def test_list_runs_ordering_deterministic(tmp_path: Path, monkeypatch) -> None:
    """Prove list_runs returns timestamp DESC, run_id DESC (newest first)."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    run_a = "2026-01-02T00:00:00Z"
    run_b = "2026-01-03T00:00:00Z"
    _write_index(config.RUN_METADATA_DIR / _sanitize(run_a), run_a, run_a)
    _write_index(config.RUN_METADATA_DIR / _sanitize(run_b), run_b, run_b)

    repo = run_repository.FileSystemRunRepository()
    runs = repo.list_runs("local", limit=10)
    assert [r["run_id"] for r in runs] == [run_b, run_a]


def test_rebuild_run_index_cli(tmp_path: Path, monkeypatch, capsys) -> None:
    """Rebuild index CLI smoke."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository
    import scripts.rebuild_run_index as rebuild_run_index

    importlib.reload(config)
    importlib.reload(run_repository)
    importlib.reload(rebuild_run_index)

    run_id = "2026-01-02T00:00:00Z"
    runs_dir = config.RUN_METADATA_DIR
    runs_dir.mkdir(parents=True, exist_ok=True)
    _write_index(runs_dir / _sanitize(run_id), run_id, run_id)

    rc = rebuild_run_index.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["results"][0]["candidate_id"] == "local"
    assert payload["results"][0]["runs_indexed"] == 1


def test_list_runs_for_profile_uses_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    run_a = "2026-01-01T00:00:00Z"
    run_b = "2026-01-02T00:00:00Z"
    run_c = "2026-01-03T00:00:00Z"
    runs_dir = config.RUN_METADATA_DIR
    _write_index(runs_dir / _sanitize(run_a), run_a, run_a, profiles=["cs", "eng"])
    _write_index(runs_dir / _sanitize(run_b), run_b, run_b, profiles=["cs"])
    _write_index(runs_dir / _sanitize(run_c), run_c, run_c, profiles=["eng"])

    repo = run_repository.FileSystemRunRepository()
    repo.rebuild_index("local")

    cs_runs = repo.list_runs_for_profile(candidate_id="local", profile="cs", limit=100)
    assert len(cs_runs) == 2
    assert cs_runs[0]["run_id"] == run_b
    assert cs_runs[1]["run_id"] == run_a
    assert "cs" in cs_runs[0]["profiles"]
    assert "cs" in cs_runs[1]["profiles"]

    eng_runs = repo.list_runs_for_profile(candidate_id="local", profile="eng", limit=100)
    assert len(eng_runs) == 2
    assert eng_runs[0]["run_id"] == run_c
    assert eng_runs[1]["run_id"] == run_a


def test_list_runs_for_profile_pages_until_enough_matches(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    runs_dir = config.RUN_METADATA_DIR
    cs_ids: list[str] = []
    for idx in range(290):
        day = 1 + (idx // 24)
        hour = idx % 24
        run_id = f"2026-01-{day:02d}T{hour:02d}:00:00Z"
        profiles = ["eng"] if idx >= 40 else ["cs"]
        if "cs" in profiles:
            cs_ids.append(run_id)
        _write_index(runs_dir / _sanitize(run_id), run_id, run_id, profiles=profiles)

    repo = run_repository.FileSystemRunRepository()
    repo.rebuild_index("local")

    rows = repo.list_runs_for_profile(candidate_id="local", profile="cs", limit=5)
    assert [row["run_id"] for row in rows] == sorted(cs_ids, reverse=True)[:5]


def test_list_runs_for_profile_pages_until_exhausted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.run_repository as run_repository

    importlib.reload(config)
    run_repository = importlib.reload(run_repository)

    runs_dir = config.RUN_METADATA_DIR
    cs_ids: list[str] = []
    for idx in range(260):
        day = 1 + (idx // 24)
        hour = idx % 24
        run_id = f"2026-02-{day:02d}T{hour:02d}:00:00Z"
        profiles = ["eng"] if idx >= 10 else ["cs"]
        if "cs" in profiles:
            cs_ids.append(run_id)
        _write_index(runs_dir / _sanitize(run_id), run_id, run_id, profiles=profiles)

    repo = run_repository.FileSystemRunRepository()
    repo.rebuild_index("local")

    rows = repo.list_runs_for_profile(candidate_id="local", profile="cs", limit=50)
    assert [row["run_id"] for row in rows] == sorted(cs_ids, reverse=True)
