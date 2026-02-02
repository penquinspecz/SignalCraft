from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import boto3
    from moto import mock_s3
except Exception:  # pragma: no cover
    boto3 = None
    mock_s3 = None

import scripts.publish_s3 as publish_s3
import scripts.verify_published_s3 as verify_published_s3


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _setup_run_dir(tmp_path: Path, run_id: str) -> Path:
    run_dir = tmp_path / "state" / "runs" / publish_s3._sanitize_run_id(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    verifiable = {
        "openai:cs:ranked_json": {"path": "openai_ranked_jobs.cs.json", "sha256": "x", "bytes": 1, "hash_algo": "sha256"},
        "openai:cs:shortlist_md": {"path": "openai_shortlist.cs.md", "sha256": "y", "bytes": 1, "hash_algo": "sha256"},
    }
    _write_json(run_dir / "run_report.json", {"run_id": run_id, "verifiable_artifacts": verifiable})
    return run_dir


def test_verify_published_s3_offline_expected_keys(tmp_path: Path, capsys) -> None:
    run_id = "2026-01-02T00:00:00Z"
    _setup_run_dir(tmp_path, run_id)
    verify_published_s3.RUN_METADATA_DIR = tmp_path / "state" / "runs"

    code = verify_published_s3.main(
        [
            "--bucket",
            "bucket",
            "--run-id",
            run_id,
            "--prefix",
            "jobintel",
            "--verify-latest",
            "--offline",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    runs_keys = payload["checked"]["runs"]
    latest_keys = payload["checked"]["latest"]
    assert runs_keys == sorted(runs_keys)
    assert latest_keys == sorted(latest_keys)
    assert any(key.endswith("openai_ranked_jobs.cs.json") for key in runs_keys)
    assert any("/latest/openai/cs/" in key for key in latest_keys)


def test_verify_published_s3_missing_verifiable_artifacts(tmp_path: Path, capsys) -> None:
    run_id = "2026-01-02T00:00:00Z"
    run_dir = tmp_path / "state" / "runs" / publish_s3._sanitize_run_id(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "run_report.json", {"run_id": run_id})
    verify_published_s3.RUN_METADATA_DIR = tmp_path / "state" / "runs"

    code = verify_published_s3.main(
        [
            "--bucket",
            "bucket",
            "--run-id",
            run_id,
            "--prefix",
            "jobintel",
            "--offline",
            "--json",
        ]
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_verify_published_s3_missing_objects(tmp_path: Path, capsys) -> None:
    if boto3 is None or mock_s3 is None:  # pragma: no cover
        pytest.skip("boto3/moto not installed")
    run_id = "2026-01-02T00:00:00Z"
    run_dir = _setup_run_dir(tmp_path, run_id)
    verify_published_s3.RUN_METADATA_DIR = tmp_path / "state" / "runs"

    with mock_s3():
        bucket = "bucket"
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=bucket)
        key = f"jobintel/runs/{run_id}/openai_ranked_jobs.cs.json"
        client.put_object(Bucket=bucket, Key=key, Body=b"[]")

        code = verify_published_s3.main(
            [
                "--bucket",
                bucket,
                "--run-id",
                run_id,
                "--prefix",
                "jobintel",
                "--verify-latest",
                "--region",
                "us-east-1",
                "--json",
            ]
        )
        assert code == 2
        payload = json.loads(capsys.readouterr().out)
        missing = payload["missing"]
        assert any(missing_key.endswith("openai_shortlist.cs.md") for missing_key in missing)
        assert any("/latest/openai/cs/" in missing_key for missing_key in missing)
