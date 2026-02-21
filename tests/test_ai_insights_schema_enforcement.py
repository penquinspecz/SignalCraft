from __future__ import annotations

import json
from pathlib import Path

from jobintel import ai_insights
from scripts.schema_validate import resolve_named_schema_path, validate_payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_ai_insights_valid_output_passes_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_insights, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    ranked = tmp_path / "ranked.json"
    _write_json(ranked, [{"job_id": "a", "title": "Role A", "score": 84}])
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    _, json_path, payload = ai_insights.generate_insights(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        prev_path=None,
        run_id="2026-02-19T00:00:00Z",
        prompt_path=prompt,
        ai_enabled=False,
        ai_reason="ai_disabled",
        model_name="stub",
    )

    schema = json.loads(resolve_named_schema_path("ai_insights_output", 1).read_text(encoding="utf-8"))
    assert validate_payload(payload, schema) == []
    assert json_path.exists()
    assert len(payload.get("actions") or []) == 5


def test_ai_insights_invalid_output_fails_closed_and_records_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_insights, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    ranked = tmp_path / "ranked.json"
    _write_json(ranked, [{"job_id": "a", "title": "Role A", "score": 84}])
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    original_builder = ai_insights._build_insights_payload
    calls = {"count": 0}

    def _first_invalid_builder(*args, **kwargs):
        calls["count"] += 1
        payload = original_builder(*args, **kwargs)
        if calls["count"] == 1:
            payload["actions"] = []
        return payload

    monkeypatch.setattr(ai_insights, "_build_insights_payload", _first_invalid_builder)

    _, json_path, payload = ai_insights.generate_insights(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        prev_path=None,
        run_id="2026-02-20T00:00:00Z",
        prompt_path=prompt,
        ai_enabled=False,
        ai_reason="ai_disabled",
        model_name="stub",
    )

    assert calls["count"] >= 2
    assert json_path.exists()
    assert payload["status"] == "error"
    assert payload["reason"] == "output_schema_validation_failed"
    metadata = payload.get("metadata") or {}
    assert "schema_errors" in metadata
    error_artifact = metadata.get("error_artifact")
    assert isinstance(error_artifact, str) and error_artifact
    assert Path(error_artifact).exists()
