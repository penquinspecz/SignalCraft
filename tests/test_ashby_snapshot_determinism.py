from __future__ import annotations

import hashlib
from pathlib import Path

from ji_engine.providers.ashby_provider import AshbyProvider, parse_ashby_snapshot_html_with_source

EXPECTED_OPENAI_SNAPSHOT_COUNT = 493
EXPECTED_OPENAI_JOB_ID_SET_SHA256 = "a868a252c488d4956540ee167f60616316bd0ce111589bdaa09d46ab0861a6ca"


def _job_id_set_hash(job_ids: list[str]) -> str:
    payload = "\n".join(job_ids).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_openai_snapshot_parse_deterministic(capsys, monkeypatch, tmp_path) -> None:
    # Determinism sentinel: fail if JSON extraction breaks or HTML fallback would be required.
    snapshot_path = Path(__file__).resolve().parents[1] / "data" / "openai_snapshots" / "index.html"
    html = snapshot_path.read_text(encoding="utf-8")

    first, source = parse_ashby_snapshot_html_with_source(html, strict=True)
    second, second_source = parse_ashby_snapshot_html_with_source(html, strict=True)

    first_ids = sorted([str(job.get("job_id") or "").strip() for job in first if job.get("job_id")])
    second_ids = sorted([str(job.get("job_id") or "").strip() for job in second if job.get("job_id")])

    assert source in {"next_data", "app_data"}
    assert source == second_source
    assert len(first) == len(second) == EXPECTED_OPENAI_SNAPSHOT_COUNT
    assert first_ids == second_ids
    assert _job_id_set_hash(first_ids) == _job_id_set_hash(second_ids)
    assert _job_id_set_hash(first_ids) == EXPECTED_OPENAI_JOB_ID_SET_SHA256

    monkeypatch.setenv("JOBINTEL_ALLOW_HTML_FALLBACK", "0")
    provider = AshbyProvider("openai", "https://jobs.ashbyhq.com/openai", tmp_path)
    provider._parse_html(html)
    captured = capsys.readouterr().out
    assert "Falling back to HTML parsing" not in captured
