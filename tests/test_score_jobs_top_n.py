from __future__ import annotations

import json
import sys
from pathlib import Path

import scripts.score_jobs as score_jobs


def test_top_n_markdown_written(tmp_path: Path, monkeypatch) -> None:
    in_path = tmp_path / "jobs.json"
    out_json = tmp_path / "ranked.json"
    out_csv = tmp_path / "ranked.csv"
    out_families = tmp_path / "families.json"
    out_md = tmp_path / "shortlist.md"
    out_top = tmp_path / "top.md"

    in_path.write_text(
        json.dumps(
            [
                {"title": "Job A", "apply_url": "https://example.com/a", "relevance": "RELEVANT"},
                {"title": "Job B", "apply_url": "https://example.com/b", "relevance": "RELEVANT"},
            ]
        ),
        encoding="utf-8",
    )

    def _fake_score(job, *_args, **_kwargs):
        score = 80 if job.get("title") == "Job A" else 60
        return {**job, "score": score, "job_id": job.get("apply_url")}

    monkeypatch.setattr(score_jobs, "score_job", _fake_score)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_jobs.py",
            "--profile",
            "cs",
            "--in_path",
            str(in_path),
            "--out_json",
            str(out_json),
            "--out_csv",
            str(out_csv),
            "--out_families",
            str(out_families),
            "--out_md",
            str(out_md),
            "--out_md_top_n",
            str(out_top),
            "--top_n",
            "1",
        ],
    )

    rc = score_jobs.main()

    assert rc == 0
    content = out_top.read_text(encoding="utf-8")
    assert "# OpenAI Top Jobs" in content
    assert "Score distribution:" in content


def test_min_score_affects_shortlist(tmp_path: Path, monkeypatch) -> None:
    in_path = tmp_path / "jobs.json"
    out_json = tmp_path / "ranked.json"
    out_csv = tmp_path / "ranked.csv"
    out_families = tmp_path / "families.json"
    out_md = tmp_path / "shortlist.md"

    in_path.write_text(
        json.dumps(
            [
                {"title": "Job A", "apply_url": "https://example.com/a", "relevance": "RELEVANT"},
                {"title": "Job B", "apply_url": "https://example.com/b", "relevance": "RELEVANT"},
            ]
        ),
        encoding="utf-8",
    )

    def _fake_score(job, *_args, **_kwargs):
        score = 55 if job.get("title") == "Job A" else 30
        return {**job, "score": score, "job_id": job.get("apply_url")}

    monkeypatch.setattr(score_jobs, "score_job", _fake_score)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_jobs.py",
            "--profile",
            "cs",
            "--in_path",
            str(in_path),
            "--out_json",
            str(out_json),
            "--out_csv",
            str(out_csv),
            "--out_families",
            str(out_families),
            "--out_md",
            str(out_md),
            "--min_score",
            "50",
        ],
    )

    rc = score_jobs.main()
    assert rc == 0
    content = out_md.read_text(encoding="utf-8")
    assert "Job A" in content
    assert "Job B" not in content


def test_explain_top_n_prints_breakdown(tmp_path: Path, monkeypatch, caplog) -> None:
    in_path = tmp_path / "jobs.json"
    out_json = tmp_path / "ranked.json"
    out_csv = tmp_path / "ranked.csv"
    out_families = tmp_path / "families.json"
    out_md = tmp_path / "shortlist.md"

    in_path.write_text(
        json.dumps(
            [
                {"title": "Customer Success Manager", "jd_text": "customer success adoption", "apply_url": "a"},
                {"title": "Research Scientist", "jd_text": "PhD model training", "apply_url": "b"},
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_jobs.py",
            "--profile",
            "cs",
            "--in_path",
            str(in_path),
            "--out_json",
            str(out_json),
            "--out_csv",
            str(out_csv),
            "--out_families",
            str(out_families),
            "--out_md",
            str(out_md),
            "--explain_top_n",
            "1",
        ],
    )

    caplog.set_level("INFO")
    rc = score_jobs.main()
    assert rc == 0
    assert "Explain top 1" in caplog.text
