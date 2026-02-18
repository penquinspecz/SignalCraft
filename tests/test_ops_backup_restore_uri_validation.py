from __future__ import annotations

from pathlib import Path

from scripts.ops import backup_onprem, restore_onprem


def test_backup_onprem_rejects_invalid_backup_uri(monkeypatch, capsys) -> None:
    monkeypatch.setenv("JOBINTEL_BACKUP_PASSPHRASE", "test-passphrase")

    called = False

    def _unexpected_client(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("boto3.client should not be called for invalid backup-uri")

    monkeypatch.setattr(backup_onprem.boto3, "client", _unexpected_client)

    rc = backup_onprem.main(["--backup-uri", "https://example.com/not-s3"])
    _out, err = capsys.readouterr()

    assert rc == 2
    assert "backup uri must start with s3://" in err
    assert called is False


def test_restore_onprem_rejects_invalid_backup_uri(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setenv("JOBINTEL_BACKUP_PASSPHRASE", "test-passphrase")

    called = False

    def _unexpected_client(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("boto3.client should not be called for invalid backup-uri")

    monkeypatch.setattr(restore_onprem.boto3, "client", _unexpected_client)

    rc = restore_onprem.main(
        [
            "--run-id",
            "m23-invalid-uri-check",
            "--backup-uri",
            "https://example.com/not-s3",
            "--restore-dir",
            str(tmp_path / "restore"),
        ]
    )
    _out, err = capsys.readouterr()

    assert rc == 2
    assert "backup uri must start with s3://" in err
    assert called is False
