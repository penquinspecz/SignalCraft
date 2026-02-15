"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ji_engine.providers.registry import load_providers_config, resolve_provider_ids

DEFAULTS_CONFIG_PATH = Path("config") / "defaults.json"


def _load_defaults(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid defaults config at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid defaults config at {path}: expected object")
    return payload


def _first_enabled_provider(providers_cfg: List[Dict[str, Any]]) -> Optional[str]:
    for entry in providers_cfg:
        provider_id = str(entry.get("provider_id") or "").strip()
        if provider_id and bool(entry.get("enabled", True)):
            return provider_id
    return None


def select_provider_ids(
    *,
    providers_arg: str | None,
    providers_config_path: Path,
    defaults_path: Path = DEFAULTS_CONFIG_PATH,
    env: Optional[Mapping[str, str]] = None,
) -> List[str]:
    env_map = env or os.environ
    providers_cfg = load_providers_config(providers_config_path)

    cli_value = (providers_arg or "").strip()
    if cli_value:
        return resolve_provider_ids(cli_value, providers_cfg)

    env_value = (env_map.get("JOBINTEL_PROVIDER_ID") or "").strip()
    if env_value:
        return resolve_provider_ids(env_value, providers_cfg)

    defaults_payload = _load_defaults(defaults_path)
    allow_fallback = bool(defaults_payload.get("allow_first_enabled_fallback", True))
    configured_default = str(defaults_payload.get("default_provider_id") or "").strip()

    if configured_default:
        try:
            return resolve_provider_ids(configured_default, providers_cfg)
        except ValueError as exc:
            err_text = str(exc)
            if not allow_fallback or (
                "Provider(s) disabled in config:" not in err_text and "Unknown provider_id(s):" not in err_text
            ):
                raise

    if allow_fallback:
        provider_id = _first_enabled_provider(providers_cfg)
        if provider_id:
            return [provider_id]

    raise ValueError(
        "No enabled providers configured. Enable at least one provider in config/providers.json "
        "or set --provider/--providers or JOBINTEL_PROVIDER_ID to an enabled provider."
    )
