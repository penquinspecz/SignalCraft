from __future__ import annotations

import json
from pathlib import Path

from jobintel import ai_insights


def test_ai_insights_stub_when_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_insights, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    ranked = tmp_path / "ranked.json"
    ranked.write_text(json.dumps([{"title": "Role A", "score": 80}]), encoding="utf-8")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    md_path, json_path, payload = ai_insights.generate_insights(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        prev_path=None,
        run_id="2026-01-22T00:00:00Z",
        prompt_path=prompt,
        ai_enabled=False,
        ai_reason="ai_disabled",
        model_name="stub",
    )

    assert json_path.exists()
    assert md_path.exists()
    assert payload["status"] == "disabled"
    assert payload["reason"] == "ai_disabled"


def test_ai_insights_metadata_hashes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_insights, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    ranked = tmp_path / "ranked.json"
    ranked.write_text(json.dumps([{"title": "Role A", "score": 80}]), encoding="utf-8")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    _, _, payload = ai_insights.generate_insights(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        prev_path=None,
        run_id="2026-01-22T00:00:00Z",
        prompt_path=prompt,
        ai_enabled=False,
        ai_reason="ai_disabled",
        model_name="stub",
    )

    meta = payload.get("metadata") or {}
    assert meta.get("prompt_version") == "weekly_insights_v1"
    assert meta.get("prompt_sha256")
    assert meta.get("input_hashes", {}).get("ranked")
