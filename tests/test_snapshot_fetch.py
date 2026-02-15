import pytest

from ji_engine.utils.network_shield import SafeGetResult
from jobintel.snapshots.fetch import fetch_html


def test_fetch_html_requests(monkeypatch):
    def fake_safe_get_text(url, *, headers, timeout_s, max_bytes, max_redirects):
        assert url == "https://example.com"
        assert timeout_s == 5
        assert max_bytes > 0
        assert max_redirects > 0
        assert headers["User-Agent"]
        return SafeGetResult(
            text="<html>ok</html>",
            status_code=200,
            final_url="https://example.com/final",
            bytes_len=len("<html>ok</html>".encode("utf-8")),
        )

    monkeypatch.setattr("jobintel.snapshots.fetch.safe_get_text", fake_safe_get_text)

    html, meta = fetch_html("https://example.com", method="requests", timeout_s=5)
    assert html == "<html>ok</html>"
    assert meta["status_code"] == 200
    assert meta["final_url"] == "https://example.com/final"
    assert meta["bytes_len"] > 0
    assert meta["error"] is None


def test_fetch_html_playwright_missing(monkeypatch):
    # Deleting sys.modules is not deterministic; site-packages can still be re-imported.
    real_import = __import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "playwright" or name.startswith("playwright."):
            raise ModuleNotFoundError("No module named 'playwright'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("jobintel.snapshots.fetch.validate_url_destination", lambda *args, **kwargs: None)
    monkeypatch.setattr("builtins.__import__", blocked_import)
    with pytest.raises(RuntimeError, match="Playwright is not installed"):
        fetch_html("https://example.com", method="playwright")


def test_fetch_html_requests_blocks_loopback() -> None:
    html, meta = fetch_html("http://127.0.0.1/", method="requests", timeout_s=5)
    assert html == ""
    assert meta["status_code"] is None
    assert meta["error"] is not None
    assert "blocked ip" in meta["error"]


def test_fetch_html_requests_blocks_link_local_metadata() -> None:
    html, meta = fetch_html("http://169.254.169.254/", method="requests", timeout_s=5)
    assert html == ""
    assert meta["status_code"] is None
    assert meta["error"] is not None
    assert "blocked ip" in meta["error"]
