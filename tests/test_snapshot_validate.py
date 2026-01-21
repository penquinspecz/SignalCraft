from pathlib import Path

from jobintel.snapshots.validate import validate_snapshot_bytes, validate_snapshot_file


def test_validate_snapshot_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    ok, reason = validate_snapshot_file("openai", path)
    assert ok is False
    assert reason == "missing file"

def test_validate_snapshot_too_small(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_SNAPSHOT_MIN_BYTES_OPENAI", "100")
    path = tmp_path / "index.html"
    path.write_text("<html></html>", encoding="utf-8")
    ok, reason = validate_snapshot_file("openai", path)
    assert ok is False
    assert "too small" in reason

def test_validate_snapshot_blocked_marker(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    path.write_text("<html>Access denied</html>", encoding="utf-8")
    ok, reason = validate_snapshot_file("openai", path)
    assert ok is False
    assert "blocked marker" in reason


def test_validate_snapshot_bytes_ok(monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_SNAPSHOT_MIN_BYTES_OPENAI", "0")
    ok, reason = validate_snapshot_bytes("openai", b"<!doctype html><html>ok</html>")
    assert ok is True
    assert reason == "ok"
