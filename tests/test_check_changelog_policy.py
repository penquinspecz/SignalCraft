from __future__ import annotations

from pathlib import Path

import scripts.check_changelog_policy as changelog_policy
from scripts.check_changelog_policy import _changed_files, _labels_from_event, evaluate_policy

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RELEASE_EVENT = FIXTURES_DIR / "github_event_pull_request_release.json"
NONRELEASE_EVENT = FIXTURES_DIR / "github_event_pull_request_nonrelease.json"


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


def test_policy_fails_for_schema_change_without_changelog() -> None:
    ok, message = evaluate_policy({"schemas/run_health.schema.v1.json"}, set())
    assert ok is False
    assert "schema contract changed" in message


def test_policy_fails_for_artifact_contract_surface_without_changelog() -> None:
    ok, message = evaluate_policy({"src/ji_engine/pipeline/artifact_paths.py"}, set())
    assert ok is False
    assert "artifact contract surface changed" in message


def test_policy_passes_when_triggered_and_changelog_present() -> None:
    ok, message = evaluate_policy({"schemas/run_summary.schema.v1.json", "CHANGELOG.md"}, set())
    assert ok is True
    assert "pass:" in message


def test_labels_from_event_payload_release_fixture() -> None:
    assert _labels_from_event(RELEASE_EVENT) == {"release", "from-codex"}


def test_labels_from_event_payload_nonrelease_fixture() -> None:
    assert _labels_from_event(NONRELEASE_EVENT) == {"from-codex", "milestone:m18"}


def test_labels_from_event_missing_payload_is_safe() -> None:
    assert _labels_from_event(Path("tests/fixtures/does-not-exist.json")) == set()


def test_main_strict_event_payload_missing_returns_2() -> None:
    code = changelog_policy.main(
        [
            "--strict-event-payload",
            "--event-path",
            str(Path("tests/fixtures/does-not-exist.json")),
            "--changed-file",
            "CHANGELOG.md",
        ]
    )
    assert code == 2


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
