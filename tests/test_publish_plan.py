from __future__ import annotations

import json
import sys
from pathlib import Path

import scripts.publish_s3 as publish_s3


def _write(path: Path, payload: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return payload


def test_publish_plan_contract(tmp_path: Path, capsys, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    run_id = "2026-01-01T00:00:00Z"
    run_dir = state_dir / "runs" / publish_s3._sanitize_run_id(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    ranked_json = data_dir / "openai_ranked_jobs.cs.json"
    ranked_csv = data_dir / "openai_ranked_jobs.cs.csv"
    _write(ranked_json, "[]")
    _write(ranked_csv, "job_id,score\n")

    publish_s3.DATA_DIR = data_dir
    publish_s3.RUN_METADATA_DIR = state_dir / "runs"

    report = {
        "run_id": run_id,
        "run_report_schema_version": 1,
        "verifiable_artifacts": {
            "openai:cs:ranked_json": {
                "path": ranked_json.name,
                "sha256": "dummy",
                "bytes": ranked_json.stat().st_size,
                "hash_algo": "sha256",
            },
            "openai:cs:ranked_csv": {
                "path": ranked_csv.name,
                "sha256": "dummy",
                "bytes": ranked_csv.stat().st_size,
                "hash_algo": "sha256",
            },
        },
    }
    (run_dir / "run_report.json").write_text(json.dumps(report), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "publish_s3.py",
            "--run-dir",
            str(run_dir),
            "--plan",
            "--json",
            "--bucket",
            "dummy",
            "--prefix",
            "jobintel",
        ],
    )
    rc = publish_s3.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    plan = payload["plan"]
    keys = [entry["s3_key"] for entry in plan]

    assert all(("runs/" in key) or ("latest/" in key) for key in keys)
    assert all(".env" not in key for key in keys)
    assert all("secret" not in key for key in keys)
    assert any(key.endswith("openai_ranked_jobs.cs.json") for key in keys)
    assert keys[:2] == [
        f"jobintel/runs/{run_id}/openai/cs/openai_ranked_jobs.cs.csv",
        f"jobintel/runs/{run_id}/openai/cs/openai_ranked_jobs.cs.json",
    ]
    assert keys[2:] == [
        "jobintel/latest/openai/cs/openai_ranked_jobs.cs.csv",
        "jobintel/latest/openai/cs/openai_ranked_jobs.cs.json",
    ]
