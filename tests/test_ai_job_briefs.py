from __future__ import annotations

import json
from pathlib import Path

from jobintel import ai_job_briefs


def _write_ranked(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "job_id": "1",
                    "title": "Role A",
                    "score": 90,
                    "fit_signals": ["fit:deployment"],
                    "risk_signals": ["risk:phd"],
                },
                {"job_id": "2", "title": "Role B", "score": 80},
            ]
        ),
        encoding="utf-8",
    )


def test_job_briefs_disabled_stub(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_job_briefs, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    ranked = tmp_path / "ranked.json"
    _write_ranked(ranked)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    _, json_path, payload = ai_job_briefs.generate_job_briefs(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        run_id="2026-01-22T00:00:00Z",
        max_jobs=2,
        max_tokens_per_job=100,
        total_budget=200,
        ai_enabled=False,
        ai_reason="ai_disabled",
        model_name="stub",
        prompt_path=prompt,
    )

    assert json_path.exists()
    assert payload["status"] == "disabled"
    assert payload["reason"] == "ai_disabled"
    accounting = (payload.get("metadata") or {}).get("ai_accounting") or {}
    assert accounting["tokens_in"] == 0
    assert accounting["tokens_out"] == 0
    assert accounting["tokens_total"] == 0
    assert accounting["estimated_cost_usd"] == "0.000000"


def test_job_briefs_cache_hit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_job_briefs, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    monkeypatch.setattr(ai_job_briefs, "STATE_DIR", tmp_path / "state")
    ranked = tmp_path / "ranked.json"
    _write_ranked(ranked)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    _, _, payload1 = ai_job_briefs.generate_job_briefs(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        run_id="2026-01-22T00:00:00Z",
        max_jobs=1,
        max_tokens_per_job=100,
        total_budget=200,
        ai_enabled=True,
        ai_reason="",
        model_name="stub",
        prompt_path=prompt,
    )
    _, _, payload2 = ai_job_briefs.generate_job_briefs(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        run_id="2026-01-22T00:00:00Z",
        max_jobs=1,
        max_tokens_per_job=100,
        total_budget=200,
        ai_enabled=True,
        ai_reason="",
        model_name="stub",
        prompt_path=prompt,
    )

    assert payload2["metadata"]["cache_hits"] >= payload1["metadata"]["cache_hits"]


def test_job_briefs_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ai_job_briefs, "RUN_METADATA_DIR", tmp_path / "state" / "runs")
    ranked = tmp_path / "ranked.json"
    _write_ranked(ranked)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    _, _, payload = ai_job_briefs.generate_job_briefs(
        provider="openai",
        profile="cs",
        ranked_path=ranked,
        run_id="2026-01-22T00:00:00Z",
        max_jobs=1,
        max_tokens_per_job=100,
        total_budget=200,
        ai_enabled=True,
        ai_reason="",
        model_name="stub",
        prompt_path=prompt,
    )

    brief = payload["briefs"][0]
    for key in ("job_id", "apply_url", "title", "score", "why_fit", "gaps", "interview_focus", "resume_tweaks"):
        assert key in brief
