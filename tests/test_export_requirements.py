from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import scripts.export_requirements as export_requirements


def test_run_pip_compile_includes_explicit_strip_extras_and_ci_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    captured: dict[str, list[str]] = {}

    def _fake_run(cmd: list[str], check: bool) -> None:
        captured["cmd"] = cmd
        assert check is True

    monkeypatch.setattr(export_requirements.subprocess, "run", _fake_run)
    export_requirements._run_pip_compile(
        requirements_in=tmp_path / "requirements.in",
        output_path=tmp_path / "requirements.txt",
        cache_dir=tmp_path / "cache",
    )

    cmd = captured["cmd"]
    assert export_requirements.PIP_COMPILE_EXTRAS_POLICY_FLAG in cmd
    assert "--pip-args=--platform manylinux_2_17_x86_64 --implementation cp --python-version 3.12 --abi cp312" in cmd


def test_render_requirements_fails_closed_in_strict_mode_on_compile_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(export_requirements, "_pip_compile_available", lambda: True)
    monkeypatch.setattr(export_requirements, "_select_pip_tools_cache_dir", lambda _repo_root: tmp_path / "cache")
    monkeypatch.setattr(export_requirements, "_ensure_ci_cache_dir", lambda: None)

    def _raise_compile_error(*_args: object, **_kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, ["piptools", "compile"])

    monkeypatch.setattr(export_requirements, "_run_pip_compile", _raise_compile_error)
    with pytest.raises(subprocess.CalledProcessError):
        export_requirements._render_requirements(["requests"], repo_root=tmp_path)
