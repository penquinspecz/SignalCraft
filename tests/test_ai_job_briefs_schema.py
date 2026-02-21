from __future__ import annotations

import json
from pathlib import Path

from jobintel import ai_job_briefs
from scripts.schema_validate import resolve_named_schema_path, validate_payload


def _write_ranked(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "job_id": "1",
                    "title": "Role A",
                    "score": 90,
                    "fit_signals": ["fit:deployment"],
                    "risk_signals": ["risk:phd"],
                }
            ]
        ),
        encoding="utf-8",
    )


def test_job_brief_schema_valid_brief_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_job_briefs, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    monkeypatch.setattr(ai_job_briefs, "STATE_DIR", tmp_path / "state")
    ranked = tmp_path / "ranked.json"
    _write_ranked(ranked)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    _, _, payload = ai_job_briefs.generate_job_briefs(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        run_id="2026-02-19T00:00:00Z",
        max_jobs=1,
        max_tokens_per_job=100,
        total_budget=200,
        ai_enabled=True,
        ai_reason="",
        model_name="stub",
        prompt_path=prompt,
    )

    assert payload["status"] == "ok"
    assert len(payload["briefs"]) == 1

    schema = json.loads(resolve_named_schema_path("ai_job_brief", 1).read_text(encoding="utf-8"))
    errors = validate_payload(payload["briefs"][0], schema)
    assert errors == []


def test_job_brief_schema_invalid_brief_fail_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_job_briefs, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    monkeypatch.setattr(ai_job_briefs, "STATE_DIR", tmp_path / "state")
    ranked = tmp_path / "ranked.json"
    _write_ranked(ranked)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    original_builder = ai_job_briefs._brief_payload

    def _invalid_brief(job):
        payload = original_builder(job)
        payload.pop("title", None)
        return payload

    monkeypatch.setattr(ai_job_briefs, "_brief_payload", _invalid_brief)

    _, json_path, payload = ai_job_briefs.generate_job_briefs(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        run_id="2026-02-20T00:00:00Z",
        max_jobs=1,
        max_tokens_per_job=100,
        total_budget=200,
        ai_enabled=True,
        ai_reason="",
        model_name="stub",
        prompt_path=prompt,
    )

    assert json_path.exists()
    assert payload["status"] == "error"
    assert payload["reason"] == "job_brief_schema_validation_failed"
    assert payload["briefs"] == []
    metadata = payload.get("metadata") or {}
    error_artifact = metadata.get("error_artifact")
    assert isinstance(error_artifact, str) and error_artifact
    assert Path(error_artifact).exists()
    assert metadata.get("schema_errors")
