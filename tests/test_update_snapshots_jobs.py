from __future__ import annotations

from pathlib import Path

import scripts.update_snapshots as update_snapshots


def test_update_snapshots_writes_job_details(tmp_path: Path, monkeypatch) -> None:
    index_html = Path("tests/fixtures/openai_index_with_apply.html").read_text(encoding="utf-8")
    detail_html = Path("tests/fixtures/ashby_job_detail.html").read_text(encoding="utf-8")

    def _fake_fetch(url: str, _timeout: float, _user_agent: str):
        if "application" in url:
            return detail_html.encode("utf-8"), 200, None
        return index_html.encode("utf-8"), 200, None

    monkeypatch.setattr(update_snapshots, "_fetch_html", _fake_fetch)

    out_dir = tmp_path / "openai_snapshots"
    manifest_path = tmp_path / "snapshot_bytes.manifest.json"
    rc = update_snapshots.main(
        [
            "--provider",
            "openai",
            "--url",
            "https://openai.com/careers/search/",
            "--out_dir",
            str(out_dir),
            "--apply",
            "--manifest-path",
            str(manifest_path),
        ]
    )

    assert rc == 0
    jobs_dir = out_dir / "jobs"
    job_one = jobs_dir / "11111111-1111-1111-1111-111111111111.html"
    job_two = jobs_dir / "22222222-2222-2222-2222-222222222222.html"
    assert job_one.exists()
    assert job_two.exists()
    assert job_one.read_text(encoding="utf-8")
    assert job_two.read_text(encoding="utf-8")


def test_update_snapshots_uses_jobs_json(tmp_path: Path, monkeypatch) -> None:
    jobs_json = tmp_path / "openai_labeled_jobs.json"
    jobs_json.write_text(
        """
[
  {"apply_url": "https://jobs.ashbyhq.com/openai/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/application"},
  {"apply_url": "https://jobs.ashbyhq.com/openai/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/application"}
]
""".strip(),
        encoding="utf-8",
    )

    detail_html = Path("tests/fixtures/ashby_job_detail.html").read_text(encoding="utf-8")

    def _fake_fetch_html(url: str, _timeout: float, _user_agent: str):
        return b"<html></html>", 200, None

    def _fake_fetch_with_retry(url: str, _timeout: float, _user_agent: str, _retries: int, _sleep_s: float):
        return detail_html.encode("utf-8"), 200, None

    monkeypatch.setattr(update_snapshots, "_fetch_html", _fake_fetch_html)
    monkeypatch.setattr(update_snapshots, "_fetch_with_retry", _fake_fetch_with_retry)

    out_dir = tmp_path / "openai_snapshots"
    manifest_path = tmp_path / "snapshot_bytes.manifest.json"
    rc = update_snapshots.main(
        [
            "--provider",
            "openai",
            "--out_dir",
            str(out_dir),
            "--jobs_json",
            str(jobs_json),
            "--apply",
            "--manifest-path",
            str(manifest_path),
        ]
    )

    assert rc == 0
    jobs_dir = out_dir / "jobs"
    assert (jobs_dir / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.html").exists()
    assert (jobs_dir / "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.html").exists()
