from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts import m21_onprem_stability_harness as harness


def _write_minimal_run_artifacts(run_dir: Path, profile: str) -> None:
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "run_summary.v1.json").write_text('{"ok":true}\n', encoding="utf-8")
    (run_dir / "run_health.v1.json").write_text('{"ok":true}\n', encoding="utf-8")
    (run_dir / "run_report.json").write_text('{"ok":true}\n', encoding="utf-8")
    (run_dir / "artifacts" / "provider_availability_v1.json").write_text('{"ok":true}\n', encoding="utf-8")
    (run_dir / "artifacts" / "explanation_v1.json").write_text('{"ok":true}\n', encoding="utf-8")
    (run_dir / "artifacts" / f"ai_insights.{profile}.json").write_text('{"ok":true}\n', encoding="utf-8")
    (run_dir / "artifacts" / f"ai_job_briefs.{profile}.error.json").write_text('{"ok":true}\n', encoding="utf-8")


def test_harness_success_writes_receipts(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "proofs"

    def fake_run(argv, capture_output, text, env, cwd, check):  # type: ignore[no-untyped-def]
        if argv[1] == "scripts/run_daily.py":
            run_id = env["JOBINTEL_RUN_ID"]
            candidate = env["JOBINTEL_CANDIDATE_ID"]
            run_dir = state_dir / "candidates" / candidate / "runs" / harness._sanitize_run_id(run_id)
            _write_minimal_run_artifacts(run_dir, "cs")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)

    exit_code = harness.main(
        [
            "--duration-hours",
            "1",
            "--interval-minutes",
            "60",
            "--max-intervals",
            "1",
            "--candidate-id",
            "local",
            "--provider",
            "openai",
            "--profile",
            "cs",
            "--state-dir",
            str(state_dir),
            "--data-dir",
            str(data_dir),
            "--output-dir",
            str(out_dir),
            "--run-id",
            "2026-02-21T12:00:00Z",
            "--skip-k8s",
            "--no-sleep",
            "--allow-run-id-drift",
        ]
    )

    assert exit_code == 0
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    final = json.loads((out_dir / "final_receipt.json").read_text(encoding="utf-8"))

    assert summary["success_count"] == 1
    assert summary["failure_count"] == 0
    assert final["status"] == "pass"
    assert final["fail_reasons"] == []


def test_harness_failure_when_pipeline_fails(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "proofs"

    def fake_run(argv, capture_output, text, env, cwd, check):  # type: ignore[no-untyped-def]
        if argv[1] == "scripts/run_daily.py":
            return SimpleNamespace(returncode=1, stdout="", stderr="pipeline failed")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)

    exit_code = harness.main(
        [
            "--duration-hours",
            "1",
            "--interval-minutes",
            "60",
            "--max-intervals",
            "1",
            "--candidate-id",
            "local",
            "--provider",
            "openai",
            "--profile",
            "cs",
            "--state-dir",
            str(state_dir),
            "--data-dir",
            str(data_dir),
            "--output-dir",
            str(out_dir),
            "--run-id",
            "2026-02-21T12:00:00Z",
            "--skip-k8s",
            "--no-sleep",
            "--allow-run-id-drift",
        ]
    )

    assert exit_code == 1
    final = json.loads((out_dir / "final_receipt.json").read_text(encoding="utf-8"))
    assert final["status"] == "fail"
    assert "no_successful_pipeline_runs" in final["fail_reasons"]
    assert "determinism_compare_not_executed" in final["fail_reasons"]
