from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import scripts.enrich_jobs as enrich_mod


def _raise_fetch(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
    raise RuntimeError("API unavailable")


def test_snapshot_fallback_extracts_text(tmp_path: Path, monkeypatch) -> None:
    snapshot_dir = tmp_path / "openai_snapshots" / "jobs"
    snapshot_dir.mkdir(parents=True)
    fixture = Path("tests/fixtures/ashby_job_detail.html").read_text(encoding="utf-8")
    job_id = "227dd1fb-d01d-462b-9e1a-4185e902860d"
    (snapshot_dir / f"{job_id}.html").write_text(fixture, encoding="utf-8")
    monkeypatch.setattr(enrich_mod, "SNAPSHOT_DIR", tmp_path / "openai_snapshots")
    monkeypatch.setenv("CAREERS_MODE", "SNAPSHOT")

    job = {
        "title": "Value Realization Lead, AI Deployment and Adoption",
        "apply_url": f"https://jobs.ashbyhq.com/openai/{job_id}/application",
        "detail_url": "/careers/value-realization-lead-ai-deployment-and-adoption-san-francisco/",
        "location": "San Francisco",
        "team": "Deployment",
        "relevance": "RELEVANT",
    }

    updated, unavailable_reason, status_key = enrich_mod._enrich_single(
        job,
        index=1,
        total=1,
        fetch_func=_raise_fetch,
    )

    assert status_key == "enriched"
    assert unavailable_reason is None
    assert isinstance(updated.get("jd_text"), str)
    assert len(updated["jd_text"]) > 200
