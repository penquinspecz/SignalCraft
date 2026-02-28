from __future__ import annotations

import json
from pathlib import Path

import scripts.replay_drift_canary as canary


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def test_normalize_provider_availability_drops_run_id_and_generated_time() -> None:
    left = {
        "run_id": "a",
        "generated_at_utc": "2026-02-28T00:00:00Z",
        "providers": [{"provider_id": "openai", "availability": "unavailable"}],
    }
    right = {
        "run_id": "b",
        "generated_at_utc": "2026-02-28T01:23:45Z",
        "providers": [{"provider_id": "openai", "availability": "unavailable"}],
    }

    assert canary._normalize_provider_availability(left) == canary._normalize_provider_availability(right)


def test_compare_identity_diff_ignores_run_id_and_timestamps(tmp_path: Path) -> None:
    left_run = tmp_path / "left"
    right_run = tmp_path / "right"

    _write_json(
        left_run / "diff.json",
        {
            "run_id": "left-run",
            "generated_at_utc": "2026-02-28T00:00:00Z",
            "provider_profile": {"openai": {"cs": {"counts": {"new": 1, "changed": 0, "removed": 0}}}},
        },
    )
    _write_json(
        right_run / "diff.json",
        {
            "run_id": "right-run",
            "generated_at_utc": "2026-02-28T03:00:00Z",
            "provider_profile": {"openai": {"cs": {"counts": {"new": 1, "changed": 0, "removed": 0}}}},
        },
    )

    ok, issue = canary._compare_identity_diff(left_run, right_run)
    assert ok is True
    assert issue is None


def test_compare_hash_manifests_reports_mismatches() -> None:
    left = {"a": "111", "b": "222"}
    right = {"a": "111", "b": "333", "c": "444"}

    mismatches = canary._compare_hash_manifests(left, right)

    assert len(mismatches) == 2
    assert "b:" in mismatches[0]
    assert "c:" in mismatches[1]
