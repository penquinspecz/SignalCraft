from __future__ import annotations

import json
from pathlib import Path

import scripts.run_daily as run_daily


def test_write_diff_summary_artifact(tmp_path: Path) -> None:
    payload = {
        "run_id": "2026-01-02T03:04:05Z",
        "generated_at": "2026-01-02T03:05:00Z",
        "provider_profile": {
            "openai": {
                "cs": {
                    "run_id": "2026-01-02T03:04:05Z",
                    "provider": "openai",
                    "profile": "cs",
                    "first_run": True,
                    "prior_run_id": None,
                    "baseline_resolved": False,
                    "baseline_source": "none",
                    "counts": {"new": 1, "changed": 0, "removed": 0},
                    "new_ids": ["job_1"],
                    "changed_ids": [],
                    "removed_ids": [],
                    "summary_hash": "abc",
                }
            }
        },
    }

    run_daily._write_diff_summary(tmp_path, payload)
    json_path = tmp_path / "diff_summary.json"
    md_path = tmp_path / "diff_summary.md"

    assert json_path.exists()
    assert md_path.exists()

    reloaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert reloaded["run_id"] == payload["run_id"]
    assert reloaded["provider_profile"]["openai"]["cs"]["counts"]["new"] == 1
    assert "openai:cs" in md_path.read_text(encoding="utf-8")
