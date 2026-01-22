from __future__ import annotations

import json
from pathlib import Path
from typing import List

from scripts.score_jobs import _compile_rules, apply_profile, load_profiles, score_job


def _scores(values: List[int]) -> dict:
    ordered = sorted(values)
    n = len(ordered)
    return {
        "p50": ordered[(n - 1) // 2],
        "p90": ordered[max(int((0.9 * n) - 1), 0)],
        "max": ordered[-1],
        "count_ge_70": sum(1 for v in ordered if v >= 70),
    }


def test_cs_scoring_distribution_targets() -> None:
    profiles = load_profiles("config/profiles.json")
    apply_profile("cs", profiles)
    pos, neg = _compile_rules()

    fixture = Path(__file__).resolve().parent / "fixtures" / "openai_enriched_jobs.sample.json"
    jobs = json.loads(fixture.read_text(encoding="utf-8"))

    scored = [score_job(j, pos, neg) for j in jobs]
    scores = [int(j.get("score", 0)) for j in scored]
    stats = _scores(scores)
    assert stats["max"] <= 100
    assert stats["p50"] >= 0
    assert stats["count_ge_70"] >= 5
