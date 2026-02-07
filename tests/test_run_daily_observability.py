from __future__ import annotations

from pathlib import Path

import scripts.run_daily as run_daily


def test_collect_run_log_pointers_is_stable(monkeypatch) -> None:
    run_id = "2026-02-07T04:40:00Z"
    log_path = "/tmp/jobintel/run.log.jsonl"
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("JOBINTEL_CLOUDWATCH_LOG_GROUP", "/aws/ecs/jobintel")
    monkeypatch.setenv("JOBINTEL_CLOUDWATCH_LOG_STREAM", "jobintel/liveproof")

    first = run_daily._collect_run_log_pointers(run_id, log_path)
    second = run_daily._collect_run_log_pointers(run_id, log_path)

    assert first == second
    assert first["schema_version"] == 1
    assert first["run_id"] == run_id
    assert first["local"]["structured_log_jsonl"] == log_path
    assert first["cloud"]["cloudwatch_log_group"] == "/aws/ecs/jobintel"
    assert first["cloud"]["cloudwatch_log_stream"] == "jobintel/liveproof"


def test_enforce_run_log_retention_prunes_logs_only(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    run_dirs = []
    for suffix in ("20260207T010000Z", "20260207T020000Z", "20260207T030000Z"):
        run_dir = runs_dir / suffix
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)
        (run_dir / "logs" / "run.log.jsonl").write_text('{"msg":"x"}\n', encoding="utf-8")
        (run_dir / "run_report.json").write_text("{}", encoding="utf-8")
        run_dirs.append(run_dir)

    summary = run_daily._enforce_run_log_retention(runs_dir=runs_dir, keep_runs=2)
    assert summary["schema_version"] == 1
    assert summary["runs_seen"] == 3
    assert summary["runs_kept"] == 2
    assert summary["log_dirs_pruned"] == 1

    oldest, middle, newest = run_dirs
    assert not (oldest / "logs").exists()
    assert (oldest / "run_report.json").exists()  # logs-only pruning, run artifacts remain
    assert (middle / "logs" / "run.log.jsonl").exists()
    assert (newest / "logs" / "run.log.jsonl").exists()
