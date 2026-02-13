from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import scripts.publish_s3 as publish_s3
from ji_engine.config import sanitize_candidate_id


def test_candidate_run_dirs_do_not_collide(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import ji_engine.config as config

    config = importlib.reload(config)
    run_safe = publish_s3._sanitize_run_id("2026-01-22T00:00:00Z")

    a = config.candidate_run_metadata_dir("alice") / run_safe
    b = config.candidate_run_metadata_dir("bob") / run_safe

    assert a != b
    assert "candidates/alice/runs" in a.as_posix()
    assert "candidates/bob/runs" in b.as_posix()


def test_candidate_publish_keys_do_not_collide(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(publish_s3, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    monkeypatch.setattr(publish_s3, "DATA_DIR", tmp_path / "data")

    ranked = tmp_path / "data" / "openai_ranked_jobs.cs.json"
    ranked.parent.mkdir(parents=True, exist_ok=True)
    ranked.write_text("[]", encoding="utf-8")

    verifiable = {
        "openai:cs:ranked_json": {
            "path": ranked.name,
            "sha256": "deadbeef",
            "bytes": ranked.stat().st_size,
            "hash_algo": "sha256",
        }
    }

    local_uploads, _ = publish_s3._build_upload_plan(
        run_id="2026-01-22T00:00:00Z",
        run_dir=tmp_path,
        prefix="jobintel",
        candidate_id="local",
        verifiable=verifiable,
        providers=["openai"],
        profiles=["cs"],
        allow_missing=False,
    )
    alice_uploads, _ = publish_s3._build_upload_plan(
        run_id="2026-01-22T00:00:00Z",
        run_dir=tmp_path,
        prefix="jobintel",
        candidate_id="alice",
        verifiable=verifiable,
        providers=["openai"],
        profiles=["cs"],
        allow_missing=False,
    )

    local_keys = {item.key for item in local_uploads}
    alice_keys = {item.key for item in alice_uploads}

    assert local_keys.isdisjoint(alice_keys)
    assert all("/candidates/alice/" in key for key in alice_keys)


def test_invalid_candidate_id_fails_closed() -> None:
    with pytest.raises(ValueError):
        sanitize_candidate_id("../escape")
