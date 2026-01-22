from __future__ import annotations

import json
from pathlib import Path

import scripts.enrich_jobs as enrich_mod


def test_missing_job_snapshots_marks_unavailable(tmp_path: Path, monkeypatch) -> None:
    labeled_path = tmp_path / "openai_labeled_jobs.json"
    out_path = tmp_path / "openai_enriched_jobs.json"
    labeled_path.write_text(
        json.dumps(
            [
                {
                    "title": "Role A",
                    "apply_url": "https://jobs.ashbyhq.com/openai/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/application",
                    "relevance": "RELEVANT",
                },
                {
                    "title": "Role B",
                    "apply_url": "https://jobs.ashbyhq.com/openai/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/application",
                    "relevance": "MAYBE",
                },
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(enrich_mod, "SNAPSHOT_DIR", tmp_path / "openai_snapshots")
    monkeypatch.setattr(enrich_mod, "_load_snapshot_detail_html", lambda _job_id: None)

    rc = enrich_mod.main(["--in_path", str(labeled_path), "--out_path", str(out_path)])
    assert rc == 0

    enriched = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(enriched) == 2
    assert all(job.get("enrich_reason") == "missing_job_snapshots" for job in enriched)
    assert all(job.get("jd_text") is None for job in enriched)
