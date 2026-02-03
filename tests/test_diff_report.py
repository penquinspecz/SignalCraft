from __future__ import annotations

from ji_engine.utils.diff_report import build_diff_markdown, build_diff_report


def test_diff_report_deterministic_ordering() -> None:
    prev = [
        {"provider": "openai", "job_id": "1", "title": "A", "apply_url": "https://a.example"},
        {"provider": "openai", "job_id": "2", "title": "B", "apply_url": "https://b.example"},
    ]
    curr = [
        {"provider": "openai", "job_id": "2", "title": "B", "apply_url": "https://b.example"},
        {"provider": "openai", "job_id": "3", "title": "C", "apply_url": "https://c.example"},
    ]
    report = build_diff_report(prev, curr, provider="openai", profile="cs", baseline_exists=True)
    report_again = build_diff_report(list(reversed(prev)), list(reversed(curr)), provider="openai", profile="cs", baseline_exists=True)

    assert report == report_again
    assert report["counts"]["added"] == 1
    assert report["counts"]["removed"] == 1
    assert report["counts"]["changed"] == 0
    assert [item["id"] for item in report["added"]]
    assert [item["id"] for item in report["removed"]]


def test_diff_markdown_includes_sections() -> None:
    report = {
        "provider": "openai",
        "profile": "cs",
        "baseline_exists": True,
        "counts": {"added": 1, "changed": 0, "removed": 0},
        "added": [{"id": "openai:1", "title": "A", "apply_url": "https://a"}],
        "changed": [],
        "removed": [],
    }
    md = build_diff_markdown(report)
    assert "# Diff since last run" in md
    assert "## Added" in md
    assert "## Changed" in md
    assert "## Removed" in md
