import json
from pathlib import Path

from ji_engine.utils.verification import compute_sha256_bytes, compute_sha256_file
from scripts import update_snapshots


def test_sha256_file(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    path.write_text("hello", encoding="utf-8")
    assert compute_sha256_file(path) == compute_sha256_bytes(b"hello")


def test_meta_write_and_atomic_overwrite(tmp_path: Path) -> None:
    out_dir = tmp_path / "snapshots"
    html_path = out_dir / "index.html"
    update_snapshots._atomic_write(html_path, b"first")
    update_snapshots._atomic_write(html_path, b"second")
    assert html_path.read_text(encoding="utf-8") == "second"

    payload = update_snapshots._build_meta(
        provider="openai",
        url="https://example.com",
        http_status=200,
        bytes_count=6,
        sha256=compute_sha256_bytes(b"second"),
        note=None,
    )
    update_snapshots._write_meta(out_dir, payload)
    meta = json.loads((out_dir / "index.meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "openai"
    assert meta["url"] == "https://example.com"
    assert meta["http_status"] == 200
    assert meta["bytes"] == 6
    assert meta["sha256"] == compute_sha256_bytes(b"second")


def test_update_snapshots_dry_run_does_not_mutate_pinned(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pinned_dir = tmp_path / "data" / "openai_snapshots"
    pinned_dir.mkdir(parents=True, exist_ok=True)
    pinned_html = pinned_dir / "index.html"
    pinned_html.write_text("old", encoding="utf-8")

    manifest_path = tmp_path / "snapshot_bytes.manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "data/openai_snapshots/index.html": {
                    "sha256": compute_sha256_bytes(b"old"),
                    "bytes": len(b"old"),
                }
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    def _fake_fetch(_url: str, _timeout: float, _user_agent: str):
        return b"new", 200, None

    monkeypatch.setattr(update_snapshots, "_fetch_html", _fake_fetch)
    monkeypatch.chdir(tmp_path)

    temp_dir = tmp_path / "tmp_refresh"
    rc = update_snapshots.main(
        [
            "--provider",
            "openai",
            "--out_dir",
            str(pinned_dir),
            "--dry-run",
            "--manifest-path",
            str(manifest_path),
            "--providers_config",
            str(repo_root / "config" / "providers.json"),
            "--temp-dir",
            str(temp_dir),
        ]
    )

    assert rc == 0
    assert pinned_html.read_text(encoding="utf-8") == "old"
    temp_html = temp_dir / "openai_snapshots" / "index.html"
    assert temp_html.read_text(encoding="utf-8") == "new"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["data/openai_snapshots/index.html"]["sha256"] == compute_sha256_bytes(b"old")


def test_update_snapshots_apply_updates_manifest(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pinned_dir = tmp_path / "data" / "openai_snapshots"
    pinned_dir.mkdir(parents=True, exist_ok=True)
    pinned_html = pinned_dir / "index.html"
    pinned_html.write_text("old", encoding="utf-8")

    manifest_path = tmp_path / "snapshot_bytes.manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "data/openai_snapshots/index.html": {
                    "sha256": compute_sha256_bytes(b"old"),
                    "bytes": len(b"old"),
                }
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    def _fake_fetch(_url: str, _timeout: float, _user_agent: str):
        return b"new", 200, None

    monkeypatch.setattr(update_snapshots, "_fetch_html", _fake_fetch)
    monkeypatch.chdir(tmp_path)

    rc = update_snapshots.main(
        [
            "--provider",
            "openai",
            "--out_dir",
            str(pinned_dir),
            "--apply",
            "--manifest-path",
            str(manifest_path),
            "--providers_config",
            str(repo_root / "config" / "providers.json"),
        ]
    )

    assert rc == 0
    assert pinned_html.read_text(encoding="utf-8") == "new"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["data/openai_snapshots/index.html"]["sha256"] == compute_sha256_bytes(b"new")
