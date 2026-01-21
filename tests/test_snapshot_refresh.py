from pathlib import Path

import pytest

from jobintel.snapshots import refresh


def test_refresh_rejects_invalid_snapshot(tmp_path: Path, monkeypatch) -> None:
    snapshot_dir = tmp_path / "openai_snapshots"
    out_path = snapshot_dir / "index.html"

    def fake_fetch_html(url, method="requests", timeout_s=30, user_agent=None, headers=None):
        return "<html>tiny</html>", {
            "method": method,
            "url": url,
            "final_url": url,
            "status_code": 200,
            "fetched_at": "2024-01-01T00:00:00+00:00",
            "bytes_len": 17,
            "error": None,
        }

    monkeypatch.setattr(refresh, "fetch_html", fake_fetch_html)
    monkeypatch.setenv("JOBINTEL_SNAPSHOT_MIN_BYTES", "1000")

    with pytest.raises(RuntimeError, match="Invalid snapshot"):
        refresh.refresh_snapshot(
            "openai",
            "https://example.com",
            out_path,
            force=False,
            timeout=1.0,
        )

    assert not out_path.exists()
    assert (snapshot_dir / "index.raw.html").exists()
    assert (snapshot_dir / "index.fetch.json").exists()
