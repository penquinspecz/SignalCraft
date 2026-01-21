from pathlib import Path

from jobintel.snapshots.refresh import is_valid_snapshot, maybe_write_snapshot


def test_is_valid_snapshot_accepts_minimal_html() -> None:
    html = "<!doctype html><html><body>hi</body></html>"
    ok, reason = is_valid_snapshot(html, min_bytes=0)
    assert ok is True
    assert reason == "ok"


def test_is_valid_snapshot_rejects_forbidden() -> None:
    html = "<html><body>403 Forbidden</body></html>"
    ok, reason = is_valid_snapshot(html, min_bytes=0)
    assert ok is False
    assert "forbidden" in reason


def test_is_valid_snapshot_rejects_captcha() -> None:
    html = "<html><body>Captcha required</body></html>"
    ok, reason = is_valid_snapshot(html, min_bytes=0)
    assert ok is False
    assert "captcha" in reason


def test_maybe_write_snapshot_only_on_valid(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    path.write_text("original", encoding="utf-8")

    invalid_html = "blocked content"
    wrote, reason = maybe_write_snapshot(path, invalid_html, force=False, min_bytes=0)
    assert wrote is False
    assert "missing html" in reason
    assert path.read_text(encoding="utf-8") == "original"

    valid_html = "<!doctype html><html><body>ok</body></html>"
    wrote, reason = maybe_write_snapshot(path, valid_html, force=False, min_bytes=0)
    assert wrote is True
    assert reason == "ok"
    assert path.read_text(encoding="utf-8") == valid_html
