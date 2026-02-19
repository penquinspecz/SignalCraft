from __future__ import annotations

from scripts.check_pr_label_policy import (
    evaluate_label_policy,
    labels_from_event_payload,
    required_label_for_branch,
)


def test_required_label_for_branch() -> None:
    assert required_label_for_branch("composer/some-task") == "from-composer"
    assert required_label_for_branch("codex/some-task") == "from-codex"
    assert required_label_for_branch("feature/some-task") is None


def test_labels_from_event_payload_extracts_names() -> None:
    payload = {"pull_request": {"labels": [{"name": "from-codex"}, {"name": "docs-only"}]}}
    assert labels_from_event_payload(payload) == {"from-codex", "docs-only"}


def test_composer_branch_requires_from_composer() -> None:
    issues = evaluate_label_policy("composer/m23", {"from-codex"})
    assert "requires label 'from-composer'" in issues[0]
    assert "should not carry provenance label 'from-codex'" in issues[1]


def test_codex_branch_passes_with_from_codex_only() -> None:
    assert evaluate_label_policy("codex/m23", {"from-codex", "docs-only"}) == []


def test_non_prefixed_branch_has_no_requirement() -> None:
    assert evaluate_label_policy("feature/m23", set()) == []
