"""
Tests for Artifact Model v2 scaffolding (Milestone 11).

Contract-first: schemas + validation tests. No pipeline emission changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.schema_validate import resolve_named_schema_path, validate_payload

# Prohibited fields in UI-safe artifacts (raw JD, secrets, etc.)
_UI_SAFE_PROHIBITED_KEYS = frozenset(
    {
        "jd_text",
        "description",
        "description_text",
        "descriptionHtml",
        "job_description",
    }
)


def _scan_for_prohibited_in_value(value: object, path: str = "") -> list[str]:
    """Recursively find prohibited keys in a JSON-serializable value."""
    violations: list[str] = []
    if isinstance(value, dict):
        for key in value:
            key_lower = key.lower() if isinstance(key, str) else ""
            if key in _UI_SAFE_PROHIBITED_KEYS or key_lower in {k.lower() for k in _UI_SAFE_PROHIBITED_KEYS}:
                violations.append(f"{path}.{key}" if path else key)
            child_path = f"{path}.{key}" if path else str(key)
            violations.extend(_scan_for_prohibited_in_value(value[key], child_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            violations.extend(_scan_for_prohibited_in_value(item, f"{path}[{idx}]"))
    return violations


def assert_ui_safe_no_raw_jd(payload: dict) -> None:
    """Assert payload does not contain prohibited raw JD fields."""
    violations = _scan_for_prohibited_in_value(payload)
    assert not violations, f"UI-safe artifact must not contain: {violations}"


def test_ui_safe_schema_loads_and_validates() -> None:
    """Schema file exists and validates a minimal conforming payload."""
    schema_path = resolve_named_schema_path("ui_safe_artifact", 1)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = {
        "ui_safe_artifact_schema_version": 1,
        "artifact_type": "ui_safe",
        "jobs": [
            {
                "job_id": "a",
                "title": "Engineer",
                "score": 85,
                "apply_url": "https://example.com/job",
            }
        ],
    }
    errors = validate_payload(payload, schema)
    assert errors == [], f"Minimal UI-safe payload should validate: {errors}"


def test_replay_safe_schema_loads_and_validates() -> None:
    """Schema file exists and validates a minimal conforming payload."""
    schema_path = resolve_named_schema_path("replay_safe_artifact", 1)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = {
        "replay_safe_artifact_schema_version": 1,
        "artifact_type": "replay_safe",
        "run_id": "2026-02-15T00:00:00Z",
        "hashes": {},
    }
    errors = validate_payload(payload, schema)
    assert errors == [], f"Minimal replay-safe payload should validate: {errors}"


def test_ui_safe_prohibition_rejects_jd_text() -> None:
    """UI-safe assertion fails when jd_text is present."""
    payload = {
        "ui_safe_artifact_schema_version": 1,
        "jobs": [
            {
                "job_id": "a",
                "title": "Engineer",
                "jd_text": "SECRET_DESCRIPTION_SHOULD_NOT_APPEAR",
            }
        ],
    }
    with pytest.raises(AssertionError, match="jd_text"):
        assert_ui_safe_no_raw_jd(payload)


def test_ui_safe_prohibition_rejects_description() -> None:
    """UI-safe assertion fails when description is present."""
    payload = {
        "ui_safe_artifact_schema_version": 1,
        "jobs": [
            {
                "job_id": "a",
                "title": "Engineer",
                "description": "raw body that should stay out",
            }
        ],
    }
    with pytest.raises(AssertionError, match="description"):
        assert_ui_safe_no_raw_jd(payload)


def test_ui_safe_prohibition_passes_without_raw_jd() -> None:
    """UI-safe assertion passes when only allowed fields present."""
    payload = {
        "ui_safe_artifact_schema_version": 1,
        "jobs": [
            {
                "job_id": "a",
                "title": "Engineer",
                "score": 90,
                "apply_url": "https://example.com/job",
                "jd_text_chars": 500,
            }
        ],
    }
    assert_ui_safe_no_raw_jd(payload)


def test_insights_input_alignment_ui_safe_no_raw_jd(tmp_path: Path) -> None:
    """Insights input output (which excludes raw JD) passes UI-safe prohibition. Aligns with test_insights_input_excludes_raw_jd_text."""
    from ji_engine.ai.insights_input import build_weekly_insights_input

    run_dir = tmp_path / "state" / "runs"
    ranked = tmp_path / "ranked.json"
    ranked.parent.mkdir(parents=True, exist_ok=True)
    ranked.write_text(
        json.dumps(
            [
                {
                    "job_id": "a",
                    "title": "Customer Success Manager",
                    "score": 88,
                    "jd_text": "SECRET_SHOULD_NOT_APPEAR",
                    "description": "raw body",
                }
            ]
        ),
        encoding="utf-8",
    )
    out_path, payload = build_weekly_insights_input(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        prev_path=None,
        ranked_families_path=None,
        run_id="2026-02-12T00:00:00Z",
        run_metadata_dir=run_dir,
    )
    serialized = out_path.read_text(encoding="utf-8")
    assert "SECRET_SHOULD_NOT_APPEAR" not in serialized
    assert "raw body" not in serialized
    assert_ui_safe_no_raw_jd(payload)


def test_existing_artifacts_categorization_documented() -> None:
    """Document which existing artifacts are UI-safe, replay-safe, or not yet categorized."""
    # Not yet categorized: run_summary, run_health, run_report, ranked_json, etc.
    # This test documents the current state. Future PRs will add categorization.
    categorized_ui_safe = []  # e.g. insights_input output when we add schema
    categorized_replay_safe = []  # e.g. run_report, scoring inputs
    not_yet_categorized = [
        "run_summary",
        "run_health",
        "run_report",
        "ranked_json",
        "ranked_csv",
        "shortlist_md",
        "enriched_jobs",
    ]
    assert len(not_yet_categorized) > 0
    assert "run_report" in not_yet_categorized
