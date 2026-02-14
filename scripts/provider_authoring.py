#!/usr/bin/env python3
from __future__ import annotations

try:
    import _bootstrap  # type: ignore
except ModuleNotFoundError:
    from scripts import _bootstrap  # noqa: F401

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from ji_engine.providers.registry import load_providers_config

PLACEHOLDER_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{provider_id} snapshot placeholder</title>
  </head>
  <body>
    <h1>{provider_id} snapshot placeholder</h1>
    <p>
      Replace this file with a real captured fixture before enabling live mode.
    </p>
    <p>
      Recommended:
      scripts/update_snapshots.py --provider {provider_id} --out_dir data/{provider_id}_snapshots --apply
    </p>
  </body>
</html>
"""


def template_entry(provider_id: str) -> Dict[str, Any]:
    pid = provider_id.strip().lower()
    if not pid:
        raise ValueError("provider_id must be non-empty")
    snapshot_dir = f"data/{pid}_snapshots"
    return {
        "provider_id": pid,
        "display_name": "Example Provider",
        "enabled": True,
        "careers_urls": ["https://example.com/careers"],
        "allowed_domains": ["example.com"],
        "extraction_mode": "jsonld",
        "mode": "snapshot",
        "snapshot_enabled": True,
        "live_enabled": False,
        "snapshot_dir": snapshot_dir,
        "snapshot_path": f"{snapshot_dir}/index.html",
        "update_cadence": {
            "min_interval_hours": 24,
            "priority": "normal",
        },
        "politeness": {
            "min_delay_s": 1.0,
            "max_attempts": 2,
        },
    }


def _validate_template(entry: Dict[str, Any]) -> None:
    payload = {"schema_version": 1, "providers": [entry]}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=True) as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        handle.flush()
        load_providers_config(Path(handle.name))


def scaffold_snapshot(provider_id: str, data_dir: Path, *, force: bool = False) -> Path:
    pid = provider_id.strip().lower()
    if not pid:
        raise ValueError("provider_id must be non-empty")
    snapshot_dir = data_dir / f"{pid}_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    index_path = snapshot_dir / "index.html"
    if index_path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing fixture: {index_path} (use --force)")
    index_path.write_text(PLACEHOLDER_TEMPLATE.format(provider_id=pid), encoding="utf-8")
    return index_path


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Provider authoring helpers (template + snapshot scaffold)")
    sub = parser.add_subparsers(dest="command", required=True)

    template_parser = sub.add_parser("template", help="Print a schema-valid provider entry template JSON")
    template_parser.add_argument("--provider-id", required=True)

    scaffold_parser = sub.add_parser("scaffold", help="Scaffold provider snapshot dir with placeholder index.html")
    scaffold_parser.add_argument("--provider-id", required=True)
    scaffold_parser.add_argument("--data-dir", default="data")
    scaffold_parser.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "template":
        entry = template_entry(args.provider_id)
        _validate_template(entry)
        print(json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.command == "scaffold":
        path = scaffold_snapshot(args.provider_id, Path(args.data_dir), force=bool(args.force))
        print(f"Wrote provider snapshot placeholder: {path}")
        return 0

    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
