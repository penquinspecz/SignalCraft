from __future__ import annotations

import json
from pathlib import Path

import scripts.check_changelog_policy as changelog_policy
from scripts.check_changelog_policy import _changed_files, _labels_from_event, evaluate_policy


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


def test_changed_files_falls_back_when_merge_base_unavailable(monkeypatch) -> None:
    calls = []

    def fake_run_git(args):
        calls.append(tuple(args))
        if args[0] == "merge-base":
            raise changelog_policy.subprocess.CalledProcessError(returncode=1, cmd=["git", *args])
        if args == ["diff", "--name-only", "origin/main..HEAD"]:
            return "pyproject.toml\nCHANGELOG.md\n"
        raise AssertionError(f"unexpected args: {args}")

    monkeypatch.setattr(changelog_policy, "_run_git", fake_run_git)
    changed = _changed_files("origin/main", "HEAD")
    assert changed == {"pyproject.toml", "CHANGELOG.md"}
    assert calls[0] == ("merge-base", "origin/main", "HEAD")
    assert calls[1] == ("diff", "--name-only", "origin/main..HEAD")
