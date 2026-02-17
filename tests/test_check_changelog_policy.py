from __future__ import annotations

import json
from pathlib import Path

from scripts.check_changelog_policy import _labels_from_event, evaluate_policy


def test_policy_skips_when_not_triggered() -> None:
    ok, message = evaluate_policy({"src/ji_engine/pipeline/runner.py"}, set())
    assert ok is True
    assert "skip:" in message


def test_policy_fails_for_release_label_without_changelog() -> None:
    ok, message = evaluate_policy({"src/ji_engine/pipeline/runner.py"}, {"release"})
    assert ok is False
    assert "CHANGELOG.md" in message
    assert "docs/RELEASE_PROCESS.md" in message


def test_policy_fails_for_version_file_without_changelog() -> None:
    ok, message = evaluate_policy({"pyproject.toml"}, set())
    assert ok is False
    assert "version file changed" in message


def test_policy_passes_when_triggered_and_changelog_present() -> None:
    ok, message = evaluate_policy({"pyproject.toml", "CHANGELOG.md"}, set())
    assert ok is True
    assert "pass:" in message


def test_labels_from_event_payload(tmp_path: Path) -> None:
    payload = {
        "pull_request": {
            "labels": [{"name": "release"}, {"name": "from-composer"}],
        }
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(payload), encoding="utf-8")
    assert _labels_from_event(event_path) == {"release", "from-composer"}
