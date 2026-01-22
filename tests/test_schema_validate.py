from pathlib import Path

import pytest

from scripts.schema_validate import validate_report


def _load_schema() -> dict:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "run_report.schema.v1.json"
    return __import__("json").loads(schema_path.read_text(encoding="utf-8"))


def test_schema_validate_ok() -> None:
    schema = _load_schema()
    report = {
        "run_report_schema_version": 1,
        "run_id": "run-1",
        "selection": {
            "scrape_provenance": {"openai": {"scrape_mode": "snapshot"}},
            "classified_job_count": 3,
            "classified_job_count_by_provider": {"openai": 3},
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
        "selection": {"scrape_provenance": {}},
    }

    errors = validate_report(report, schema)
    assert errors
    assert any("classified_job_count" in err for err in errors)
    assert any("classified_job_count_by_provider" in err for err in errors)
