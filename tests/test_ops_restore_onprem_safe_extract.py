from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from scripts.ops import restore_onprem


def _add_file(tf: tarfile.TarFile, name: str, content: bytes, *, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    info.mode = mode
    tf.addfile(info, io.BytesIO(content))


def test_safe_extract_tar_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad-parent.tar"
    with tarfile.open(archive, "w") as tf:
        _add_file(tf, "../pwned", b"owned")

    dest = tmp_path / "restore"
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r") as tf:
        with pytest.raises(RuntimeError, match=r"unsafe tar member path: \.\./pwned"):
            restore_onprem._safe_extract_tar(tf, dest)

    assert not (tmp_path / "pwned").exists()
    assert list(dest.rglob("*")) == []


def test_safe_extract_tar_rejects_absolute_path(tmp_path: Path) -> None:
    archive = tmp_path / "bad-absolute.tar"
    with tarfile.open(archive, "w") as tf:
        _add_file(tf, "/etc/passwd", b"nope")

    dest = tmp_path / "restore"
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r") as tf:
        with pytest.raises(RuntimeError, match=r"unsafe tar member path: /etc/passwd"):
            restore_onprem._safe_extract_tar(tf, dest)

    assert list(dest.rglob("*")) == []


def test_safe_extract_tar_rejects_symlink_member(tmp_path: Path) -> None:
    archive = tmp_path / "bad-symlink.tar"
    with tarfile.open(archive, "w") as tf:
        link = tarfile.TarInfo(name="state/latest")
        link.type = tarfile.SYMTYPE
        link.linkname = "../state/runs"
        tf.addfile(link)

    dest = tmp_path / "restore"
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r") as tf:
        with pytest.raises(RuntimeError, match=r"unsafe tar member type: state/latest"):
            restore_onprem._safe_extract_tar(tf, dest)

    assert list(dest.rglob("*")) == []


def test_safe_extract_tar_extracts_safe_members_and_strips_special_mode_bits(tmp_path: Path) -> None:
    archive = tmp_path / "safe.tar"
    with tarfile.open(archive, "w") as tf:
        dir_info = tarfile.TarInfo(name="state/runs")
        dir_info.type = tarfile.DIRTYPE
        dir_info.mode = 0o2755
        tf.addfile(dir_info)
        _add_file(tf, "state/runs/index.json", b'{"ok":true}\n', mode=0o4755)

    dest = tmp_path / "restore"
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r") as tf:
        restore_onprem._safe_extract_tar(tf, dest)

    extracted_dir = dest / "state" / "runs"
    extracted_file = extracted_dir / "index.json"
    assert extracted_file.read_text(encoding="utf-8") == '{"ok":true}\n'
    assert extracted_dir.exists()
    assert (extracted_dir.stat().st_mode & 0o7777) == 0o755
    assert (extracted_file.stat().st_mode & 0o7777) == 0o755
