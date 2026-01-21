from pathlib import Path

from jobintel.snapshots.validate import validate_snapshot_file


def test_validate_snapshot_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    ok, reason = validate_snapshot_file(path, min_bytes=1)
    assert ok is False
    assert reason == "missing file"


def test_validate_snapshot_too_small(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    path.write_text("<html></html>", encoding="utf-8")
    ok, reason = validate_snapshot_file(path, min_bytes=100)
    assert ok is False
    assert "too small" in reason


def test_validate_snapshot_blocked_marker(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    path.write_text("<html>Access denied</html>", encoding="utf-8")
    ok, reason = validate_snapshot_file(path, min_bytes=0)
    assert ok is False
    assert "blocked marker" in reason
