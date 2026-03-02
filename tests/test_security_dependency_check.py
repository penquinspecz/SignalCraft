"""Tests for security dependency check exit code behavior."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts import security_dependency_check

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "security_dependency_check.py"


class TestExitCodes:
    def test_exit_0_on_clean_scan(self, monkeypatch) -> None:
        """Exit 0 when scan completes with no vulnerabilities."""
        monkeypatch.setattr(
            security_dependency_check,
            "parse_args",
            lambda: argparse.Namespace(requirements=["requirements.txt"], attempts=1, sleep_seconds=0.0),
        )
        monkeypatch.setattr(security_dependency_check, "_run_pip_audit", lambda _: (0, ""))

        assert security_dependency_check.main() == 0

    def test_exit_1_on_vulnerabilities(self, monkeypatch) -> None:
        """Exit 1 when vulnerabilities are reported."""
        monkeypatch.setattr(
            security_dependency_check,
            "parse_args",
            lambda: argparse.Namespace(requirements=["requirements.txt"], attempts=1, sleep_seconds=0.0),
        )
        monkeypatch.setattr(
            security_dependency_check,
            "_run_pip_audit",
            lambda _: (1, "Found 1 known vulnerability in 1 package"),
        )

        assert security_dependency_check.main() == 1

    def test_exit_2_on_infra_unavailable(self, monkeypatch) -> None:
        """Exit 2 when advisory database is unreachable."""
        monkeypatch.setattr(
            security_dependency_check,
            "parse_args",
            lambda: argparse.Namespace(requirements=["requirements.txt"], attempts=2, sleep_seconds=0.0),
        )
        attempts = iter([(1, "HTTPSConnectionPool: Read timed out"), (1, "service unavailable")])
        monkeypatch.setattr(security_dependency_check, "_run_pip_audit", lambda _: next(attempts))
        monkeypatch.setattr(security_dependency_check.time, "sleep", lambda _: None)

        assert security_dependency_check.main() == 2

    def test_exit_codes_documented_in_script(self) -> None:
        """Script should document exit codes in docstring or comments."""
        text = SCRIPT.read_text(encoding="utf-8").lower()
        assert "exit 0" in text or "exit code 0" in text
        assert "exit 1" in text or "exit code 1" in text
        assert "exit 2" in text or "exit code 2" in text
