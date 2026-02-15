from __future__ import annotations

import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pytest

import ji_engine.config as config
import scripts.run_daily as run_daily_module
from ji_engine.providers.selection import select_provider_ids


def _write_provider_config(path: Path, *, openai_enabled: bool, anthropic_enabled: bool) -> None:
    payload = {
        "schema_version": 1,
        "providers": [
            {
                "provider_id": "openai",
                "name": "OpenAI",
                "careers_urls": ["https://openai.com/careers"],
                "allowed_domains": ["openai.com"],
                "extraction_mode": "jsonld",
                "mode": "snapshot",
                "snapshot_path": "data/openai_snapshots/index.html",
                "live_enabled": False,
                "enabled": openai_enabled,
            },
            {
                "provider_id": "anthropic",
                "name": "Anthropic",
                "careers_urls": ["https://www.anthropic.com/careers"],
                "allowed_domains": ["anthropic.com"],
                "extraction_mode": "jsonld",
                "mode": "snapshot",
                "snapshot_path": "data/anthropic_snapshots/index.html",
                "live_enabled": False,
                "enabled": anthropic_enabled,
            },
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_defaults(path: Path, *, default_provider_id: str = "openai", allow_fallback: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "default_provider_id": default_provider_id,
                "allow_first_enabled_fallback": allow_fallback,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_select_provider_ids_falls_back_when_config_default_disabled(tmp_path: Path) -> None:
    providers_path = tmp_path / "providers.json"
    defaults_path = tmp_path / "defaults.json"
    _write_provider_config(providers_path, openai_enabled=False, anthropic_enabled=True)
    _write_defaults(defaults_path, default_provider_id="openai", allow_fallback=True)

    selected = select_provider_ids(
        providers_arg="",
        providers_config_path=providers_path,
        defaults_path=defaults_path,
        env={},
    )
    assert selected == ["anthropic"]


def test_select_provider_ids_fails_when_no_enabled_providers(tmp_path: Path) -> None:
    providers_path = tmp_path / "providers.json"
    defaults_path = tmp_path / "defaults.json"
    _write_provider_config(providers_path, openai_enabled=False, anthropic_enabled=False)
    _write_defaults(defaults_path, default_provider_id="openai", allow_fallback=True)

    with pytest.raises(ValueError, match="No enabled providers configured"):
        select_provider_ids(
            providers_arg="",
            providers_config_path=providers_path,
            defaults_path=defaults_path,
            env={},
        )


def test_select_provider_ids_explicit_disabled_provider_fails(tmp_path: Path) -> None:
    providers_path = tmp_path / "providers.json"
    defaults_path = tmp_path / "defaults.json"
    _write_provider_config(providers_path, openai_enabled=False, anthropic_enabled=True)
    _write_defaults(defaults_path, default_provider_id="openai", allow_fallback=True)

    with pytest.raises(ValueError, match="Provider\\(s\\) disabled in config: openai"):
        select_provider_ids(
            providers_arg="openai",
            providers_config_path=providers_path,
            defaults_path=defaults_path,
            env={},
        )


def test_run_daily_succeeds_with_openai_disabled_when_anthropic_enabled(tmp_path: Path, monkeypatch: Any) -> None:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    providers_path = tmp_path / "providers.json"
    defaults_path = tmp_path / "defaults.json"
    data_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    _write_provider_config(providers_path, openai_enabled=False, anthropic_enabled=True)
    _write_defaults(defaults_path, default_provider_id="openai", allow_fallback=True)

    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(state_dir))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    monkeypatch.setenv("JOBINTEL_RUN_ID", "2026-02-15T00:00:00Z")

    import ji_engine.providers.selection as provider_selection

    monkeypatch.setattr(provider_selection, "DEFAULTS_CONFIG_PATH", defaults_path)
    importlib.reload(config)
    run_daily = importlib.reload(run_daily_module)

    def fake_run(_cmd: list[str], *, stage: str) -> None:
        if stage == "scrape":
            output_dir = data_dir / "ashby_cache"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "anthropic_raw_jobs.json").write_text("[]", encoding="utf-8")
            (output_dir / "anthropic_scrape_meta.json").write_text(
                json.dumps({"scrape_mode": "snapshot", "parsed_job_count": 1}, sort_keys=True),
                encoding="utf-8",
            )

    monkeypatch.setattr(run_daily, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_daily.py",
            "--no_subprocess",
            "--scrape_only",
            "--profiles",
            "cs",
            "--providers-config",
            str(providers_path),
        ],
    )

    assert run_daily.main() == 0


def test_run_daily_fails_with_clear_error_when_all_providers_disabled(
    tmp_path: Path, monkeypatch: Any, caplog: pytest.LogCaptureFixture
) -> None:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    providers_path = tmp_path / "providers.json"
    defaults_path = tmp_path / "defaults.json"
    data_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    _write_provider_config(providers_path, openai_enabled=False, anthropic_enabled=False)
    _write_defaults(defaults_path, default_provider_id="openai", allow_fallback=True)

    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(state_dir))

    import ji_engine.providers.selection as provider_selection

    monkeypatch.setattr(provider_selection, "DEFAULTS_CONFIG_PATH", defaults_path)
    importlib.reload(config)
    run_daily = importlib.reload(run_daily_module)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_daily.py",
            "--no_subprocess",
            "--scrape_only",
            "--profiles",
            "cs",
            "--providers-config",
            str(providers_path),
        ],
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit) as exc:
            run_daily.main()
    assert exc.value.code == 2
    assert "No enabled providers configured" in caplog.text


def test_run_daily_fails_with_clear_error_for_explicit_disabled_provider(
    tmp_path: Path, monkeypatch: Any, caplog: pytest.LogCaptureFixture
) -> None:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    providers_path = tmp_path / "providers.json"
    defaults_path = tmp_path / "defaults.json"
    data_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    _write_provider_config(providers_path, openai_enabled=False, anthropic_enabled=True)
    _write_defaults(defaults_path, default_provider_id="openai", allow_fallback=True)

    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(state_dir))

    import ji_engine.providers.selection as provider_selection

    monkeypatch.setattr(provider_selection, "DEFAULTS_CONFIG_PATH", defaults_path)
    importlib.reload(config)
    run_daily = importlib.reload(run_daily_module)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_daily.py",
            "--no_subprocess",
            "--scrape_only",
            "--providers",
            "openai",
            "--profiles",
            "cs",
            "--providers-config",
            str(providers_path),
        ],
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit) as exc:
            run_daily.main()
    assert exc.value.code == 2
    assert "Provider(s) disabled in config: openai" in caplog.text
