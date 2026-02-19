from __future__ import annotations

from pathlib import Path

from ji_engine.pipeline.run_pathing import sanitize_run_id


def run_metadata_path(run_metadata_dir: Path, run_id: str) -> Path:
    safe_id = sanitize_run_id(run_id)
    return run_metadata_dir / f"{safe_id}.json"


def run_health_path(run_dir: Path) -> Path:
    return run_dir / "run_health.v1.json"


def run_summary_path(run_dir: Path) -> Path:
    return run_dir / "run_summary.v1.json"


def provider_availability_path(run_dir: Path) -> Path:
    return run_dir / "artifacts" / "provider_availability_v1.json"


def run_audit_path(run_dir: Path) -> Path:
    return run_dir / "artifacts" / "run_audit_v1.json"


def explanation_path(run_dir: Path) -> Path:
    return run_dir / "artifacts" / "explanation_v1.json"
