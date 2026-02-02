from pathlib import Path

import pytest

from scripts.schema_validate import resolve_schema_path, validate_report


def _load_schema() -> dict:
    schema_path = resolve_schema_path(1)
    return __import__("json").loads(schema_path.read_text(encoding="utf-8"))


def test_schema_validate_ok() -> None:
    schema = _load_schema()
    report = {
        "run_report_schema_version": 1,
        "run_id": "run-1",
        "verifiable_artifacts": {},
        "config_fingerprint": "a" * 64,
        "environment_fingerprint": {
            "python_version": "3.10.14",
            "platform": "test",
            "image_tag": None,
            "git_sha": None,
        },
        "flags": {"min_score": 40, "min_alert_score": 80},
        "selection": {
            "scrape_provenance": {"openai": {"scrape_mode": "snapshot"}},
            "classified_job_count": 3,
            "classified_job_count_by_provider": {"openai": 3},
        },
        "scoring_input_selection_by_profile": {
            "cs": {
                "selected_path": "/tmp/enriched.json",
                "candidate_paths_considered": [
                    {"path": "/tmp/ai.json", "exists": False, "mtime_iso": None, "sha256": None},
                    {"path": "/tmp/enriched.json", "exists": True, "mtime_iso": None, "sha256": "abc"},
                ],
                "selection_reason": "default_enriched_required",
                "comparison_details": {"newer_by_seconds": 1.0, "prefer_ai": False},
                "decision": {"rule": "default_enriched_required"},
            }
        },
        "delta_summary": {
            "provider_profile": {
                "openai": {
                    "cs": {
                        "labeled_total": 3,
                        "ranked_total": 5,
                        "new_job_count": 0,
                        "removed_job_count": 0,
                        "changed_job_count": 0,
                        "unchanged_job_count": 0,
                        "change_fields": {"title": 0, "location": 0, "team": 0, "url": 0},
                        "baseline_run_id": None,
                    }
                }
            }
        },
    }

    assert validate_report(report, schema) == []


def test_schema_validate_missing_required() -> None:
    schema = _load_schema()
    report = {
        "run_report_schema_version": 1,
        "run_id": "run-1",
        "verifiable_artifacts": {},
        "config_fingerprint": "a" * 64,
        "environment_fingerprint": {
            "python_version": "3.10.14",
            "platform": "test",
            "image_tag": None,
            "git_sha": None,
        },
        "selection": {"scrape_provenance": {}},
    }

    errors = validate_report(report, schema)
    assert errors
    assert any("classified_job_count" in err for err in errors)
    assert any("classified_job_count_by_provider" in err for err in errors)


def test_schema_validate_selection_reason_enum() -> None:
    schema = _load_schema()
    report = {
        "run_report_schema_version": 1,
        "run_id": "run-1",
        "verifiable_artifacts": {},
        "config_fingerprint": "a" * 64,
        "environment_fingerprint": {
            "python_version": "3.10.14",
            "platform": "test",
            "image_tag": None,
            "git_sha": None,
        },
        "selection": {
            "scrape_provenance": {"openai": {"scrape_mode": "snapshot"}},
            "classified_job_count": 3,
            "classified_job_count_by_provider": {"openai": 3},
        },
        "scoring_input_selection_by_profile": {
            "cs": {
                "selected_path": "/tmp/enriched.json",
                "candidate_paths_considered": [],
                "selection_reason": "not_valid",
                "comparison_details": {"newer_by_seconds": 1.0},
            }
        },
    }

    errors = validate_report(report, schema)
    assert any("not in enum" in err for err in errors)


def test_resolve_schema_path_repo() -> None:
    schema_path = resolve_schema_path(1)
    assert schema_path.name == "run_report.schema.v1.json"
    assert schema_path.exists()


def test_resolve_schema_path_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override_dir = tmp_path / "schemas"
    override_dir.mkdir()
    schema_path = override_dir / "run_report.schema.v1.json"
    schema_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("JOBINTEL_SCHEMA_DIR", str(override_dir))
    resolved = resolve_schema_path(1)
    assert resolved == schema_path
