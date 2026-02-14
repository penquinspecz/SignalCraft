from __future__ import annotations

import json
from pathlib import Path

import pytest

from ji_engine.providers.registry import load_providers_config
from scripts import provider_authoring


def test_template_command_outputs_schema_valid_entry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = provider_authoring.main(["template", "--provider-id", "exampleco"])
    assert rc == 0
    rendered = capsys.readouterr().out
    entry = json.loads(rendered)
    assert entry["provider_id"] == "exampleco"
    assert entry["live_enabled"] is False
    assert entry["mode"] == "snapshot"
    payload = {"schema_version": 1, "providers": [entry]}
    temp = tmp_path / "providers.json"
    try:
        temp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        loaded = load_providers_config(temp)
    finally:
        temp.unlink(missing_ok=True)
    assert loaded[0]["provider_id"] == "exampleco"


def test_scaffold_creates_snapshot_placeholder(tmp_path: Path) -> None:
    rc = provider_authoring.main(
        [
            "scaffold",
            "--provider-id",
            "acme",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    expected = tmp_path / "acme_snapshots" / "index.html"
    assert expected.exists()
    body = expected.read_text(encoding="utf-8")
    assert "acme snapshot placeholder" in body
    assert "update_snapshots.py --provider acme" in body


def test_scaffold_refuses_overwrite_without_force(tmp_path: Path) -> None:
    target = tmp_path / "acme_snapshots" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite existing fixture"):
        provider_authoring.main(
            [
                "scaffold",
                "--provider-id",
                "acme",
                "--data-dir",
                str(tmp_path),
            ]
        )
