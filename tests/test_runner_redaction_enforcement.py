from __future__ import annotations

import importlib
import logging
from pathlib import Path

import pytest


def _reload_runner():
    import ji_engine.pipeline.runner as runner

    return importlib.reload(runner)


def _reload_redaction_guard():
    import ji_engine.pipeline.redaction_guard as redaction_guard

    return importlib.reload(redaction_guard)


def test_redaction_guard_json_fail_closed_when_enforced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("REDACTION_ENFORCE", "1")
    runner = _reload_runner()
    with pytest.raises(RuntimeError, match="Potential secret-like JSON content detected"):
        runner._redaction_guard_json(
            tmp_path / "artifact.json",
            {"auth": "Bearer token_abcdefghijklmnopqrstuvwxyz12345"},
        )


def test_redaction_guard_warns_when_not_enforced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("REDACTION_ENFORCE", raising=False)
    runner = _reload_runner()
    with caplog.at_level(logging.WARNING):
        runner._redaction_guard_text(
            tmp_path / "artifact.txt",
            "Authorization: Bearer token_abcdefghijklmnopqrstuvwxyz12345",
        )
    assert any("Potential secret-like content detected" in rec.message for rec in caplog.records)


def test_redaction_module_guard_json_fail_closed_when_enforced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("REDACTION_ENFORCE", "1")
    redaction_guard = _reload_redaction_guard()
    with pytest.raises(RuntimeError, match="Potential secret-like JSON content detected"):
        redaction_guard.redaction_guard_json(
            tmp_path / "artifact.json",
            {"auth": "Bearer token_abcdefghijklmnopqrstuvwxyz12345"},
        )


def test_redaction_module_guard_text_warns_when_not_enforced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("REDACTION_ENFORCE", raising=False)
    redaction_guard = _reload_redaction_guard()
    with caplog.at_level(logging.WARNING):
        redaction_guard.redaction_guard_text(
            tmp_path / "artifact.txt",
            "Authorization: Bearer token_abcdefghijklmnopqrstuvwxyz12345",
        )
    assert any("Potential secret-like content detected" in rec.message for rec in caplog.records)
