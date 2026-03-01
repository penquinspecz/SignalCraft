"""
Tests for artifact catalog (Artifact Model v2 enforcement).
"""

from __future__ import annotations

import json

import pytest

from ji_engine.artifacts.catalog import (
    FORBIDDEN_JD_KEYS,
    ArtifactCategory,
    get_artifact_category,
    redact_forbidden_fields,
    validate_artifact_payload,
)


def test_get_artifact_category_exact() -> None:
    assert get_artifact_category("run_summary.v1.json") == ArtifactCategory.UI_SAFE
    assert get_artifact_category("run_health.v1.json") == ArtifactCategory.REPLAY_SAFE
    assert get_artifact_category("run_report.json") == ArtifactCategory.REPLAY_SAFE
    assert get_artifact_category("provider_availability_v1.json") == ArtifactCategory.UI_SAFE
    assert get_artifact_category("explanation_v1.json") == ArtifactCategory.UI_SAFE
    assert get_artifact_category("digest_v1.json") == ArtifactCategory.UI_SAFE
    assert get_artifact_category("job_timeline_v1.json") == ArtifactCategory.UI_SAFE
    assert get_artifact_category("digest_receipt_v1.json") == ArtifactCategory.REPLAY_SAFE


def test_get_artifact_category_patterns() -> None:
    assert get_artifact_category("openai_ranked_jobs.cs.json") == ArtifactCategory.REPLAY_SAFE
    assert get_artifact_category("ai_insights.cs.json") == ArtifactCategory.UI_SAFE
    assert get_artifact_category("ai_job_briefs.cs.json") == ArtifactCategory.UI_SAFE


def test_get_artifact_category_uncategorized() -> None:
    assert get_artifact_category("unknown_artifact.json") == ArtifactCategory.UNCATEGORIZED
    assert get_artifact_category("mystery.json") == ArtifactCategory.UNCATEGORIZED


def test_validate_artifact_payload_uncategorized_raises() -> None:
    with pytest.raises(ValueError) as exc_info:
        validate_artifact_payload(
            {"foo": "bar"},
            "unknown.json",
            "run-123",
            ArtifactCategory.UNCATEGORIZED,
        )
    detail = json.loads(str(exc_info.value))
    assert detail["error"] == "artifact_uncategorized"
    assert detail["artifact_key"] == "unknown.json"
    assert detail["run_id"] == "run-123"


def test_validate_artifact_payload_ui_safe_rejects_jd_text() -> None:
    with pytest.raises(ValueError) as exc_info:
        validate_artifact_payload(
            {"jobs": [{"job_id": "j1", "jd_text": "forbidden"}]},
            "ai_insights.cs.json",
            "run-123",
            ArtifactCategory.UI_SAFE,
        )
    detail = json.loads(str(exc_info.value))
    assert detail["error"] == "ui_safe_prohibition_violation"
    assert "jd_text" in str(detail["violations"])


def test_validate_artifact_payload_ui_safe_passes_without_prohibited() -> None:
    validate_artifact_payload(
        {"metadata": {"v": 1}, "jobs": [{"job_id": "j1", "title": "Engineer"}]},
        "ai_insights.cs.json",
        "run-123",
        ArtifactCategory.UI_SAFE,
    )


def test_redact_forbidden_fields_removes_jd_keys() -> None:
    """redact_forbidden_fields strips jd_text, description, etc. recursively."""
    assert FORBIDDEN_JD_KEYS
    inp = {
        "job_id": "j1",
        "jd_text": "secret JD",
        "description": "forbidden",
        "title": "Engineer",
        "nested": {"job_description": "also forbidden", "ok": True},
    }
    out = redact_forbidden_fields(inp)
    assert isinstance(out, dict)
    assert out.get("job_id") == "j1"
    assert out.get("title") == "Engineer"
    assert "jd_text" not in out
    assert "description" not in out
    assert out.get("nested", {}).get("ok") is True
    assert "job_description" not in out.get("nested", {})
