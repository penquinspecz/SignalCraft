from __future__ import annotations

from pathlib import Path


def test_ci_smoke_gate_doc_exists_with_required_headings() -> None:
    path = Path("docs/CI_SMOKE_GATE.md")
    assert path.exists(), "docs/CI_SMOKE_GATE.md is required"
    text = path.read_text(encoding="utf-8")
    for heading in (
        "# CI Smoke Gate Contract",
        "## CI Step Order",
        "## Gate Contracts",
        "## Failure Modes And What To Inspect",
        "## Reproduce CI Smoke Locally",
    ):
        assert heading in text, f"Missing heading in CI smoke gate doc: {heading}"
