from types import SimpleNamespace

import pytest

from jobintel.snapshots.fetch import fetch_html


def test_fetch_html_requests(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        return SimpleNamespace(
            text="<html>ok</html>",
            status_code=200,
            url="https://example.com/final",
        )

    monkeypatch.setattr("jobintel.snapshots.fetch.requests.get", fake_get)

    html, meta = fetch_html("https://example.com", method="requests", timeout_s=5)
    assert html == "<html>ok</html>"
    assert meta["status_code"] == 200
    assert meta["final_url"] == "https://example.com/final"
    assert meta["bytes_len"] > 0
    assert meta["error"] is None


def test_fetch_html_playwright_missing(monkeypatch):
    import sys

    monkeypatch.delitem(sys.modules, "playwright", raising=False)
    monkeypatch.delitem(sys.modules, "playwright.sync_api", raising=False)
    with pytest.raises(RuntimeError, match="Playwright is not installed"):
        fetch_html("https://example.com", method="playwright")
