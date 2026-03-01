from __future__ import annotations

from pathlib import Path

from ji_engine.pipeline.artifact_paths import (
    digest_path,
    digest_receipt_path,
    provider_availability_path,
    run_audit_path,
    run_health_path,
    run_metadata_path,
    run_summary_path,
)


def test_run_metadata_path_sanitizes_run_id() -> None:
    run_metadata_dir = Path("/tmp/jobintel/state/runs")
    path = run_metadata_path(run_metadata_dir, "2026-02-19T03:04:14.123Z")
    assert path == Path("/tmp/jobintel/state/runs/20260219T030414123Z.json")


def test_run_registry_paths_match_contract_filenames(tmp_path: Path) -> None:
    run_dir = tmp_path / "state" / "candidates" / "local" / "runs" / "run-123"

    assert run_health_path(run_dir) == run_dir / "run_health.v1.json"
    assert run_summary_path(run_dir) == run_dir / "run_summary.v1.json"
    assert provider_availability_path(run_dir) == run_dir / "artifacts" / "provider_availability_v1.json"
    assert run_audit_path(run_dir) == run_dir / "artifacts" / "run_audit_v1.json"
    assert digest_path(run_dir) == run_dir / "artifacts" / "digest_v1.json"
    assert digest_receipt_path(run_dir) == run_dir / "artifacts" / "digest_receipt_v1.json"
