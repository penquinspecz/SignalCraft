from __future__ import annotations

import os
from pathlib import Path

import scripts.run_daily as run_daily


class _Args:
    def __init__(self, *, no_enrich: bool, ai: bool, ai_only: bool) -> None:
        self.no_enrich = no_enrich
        self.ai = ai
        self.ai_only = ai_only


def _touch(path: Path, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    os.utime(path, (mtime, mtime))


_ALLOWED = {
    "ai_only",
    "no_enrich_enriched_newer",
    "no_enrich_labeled_newer_or_equal",
    "no_enrich_enriched_only",
    "no_enrich_labeled_only",
    "no_enrich_missing",
    "default_enriched_required",
    "default_enriched_missing",
    "prefer_ai_enriched",
}


def test_selection_reason_no_enrich_enriched_newer(tmp_path: Path, monkeypatch) -> None:
    enriched = tmp_path / "enriched.json"
    labeled = tmp_path / "labeled.json"
    ai = tmp_path / "ai.json"
    _touch(labeled, 10)
    _touch(enriched, 20)

    monkeypatch.setattr(run_daily, "_provider_enriched_jobs_json", lambda _p: enriched)
    monkeypatch.setattr(run_daily, "_provider_labeled_jobs_json", lambda _p: labeled)
    monkeypatch.setattr(run_daily, "_provider_ai_jobs_json", lambda _p: ai)

    detail = run_daily._score_input_selection_detail_for(_Args(no_enrich=True, ai=False, ai_only=False), "openai")
    assert detail["selection_reason"] == "no_enrich_enriched_newer"
    assert detail["selected_path"] == str(enriched)
    assert detail["selection_reason"] in _ALLOWED


def test_selection_reason_prefer_ai(tmp_path: Path, monkeypatch) -> None:
    enriched = tmp_path / "enriched.json"
    labeled = tmp_path / "labeled.json"
    ai = tmp_path / "ai.json"
    _touch(labeled, 10)
    _touch(enriched, 20)
    _touch(ai, 30)

    monkeypatch.setattr(run_daily, "_provider_enriched_jobs_json", lambda _p: enriched)
    monkeypatch.setattr(run_daily, "_provider_labeled_jobs_json", lambda _p: labeled)
    monkeypatch.setattr(run_daily, "_provider_ai_jobs_json", lambda _p: ai)

    detail = run_daily._score_input_selection_detail_for(_Args(no_enrich=False, ai=True, ai_only=False), "openai")
    assert detail["selection_reason"] == "prefer_ai_enriched"
    assert detail["selected_path"] == str(ai)
    assert detail["selection_reason"] in _ALLOWED
