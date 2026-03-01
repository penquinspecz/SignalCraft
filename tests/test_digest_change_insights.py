from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from ji_engine.artifacts.catalog import assert_no_forbidden_fields

_JD_LEAK_MARKER = "DIGEST_CHANGE_INSIGHTS_JD_LEAK_MARKER"


def _timeline_payload() -> Dict[str, Any]:
    return {
        "jobs": [
            {
                "job_hash": "a" * 64,
                "provider_id": "openai",
                "canonical_url": "https://example.com/jobs/a",
                "observations": [
                    {
                        "observation_id": "obs-a-1",
                        "observed_at_utc": "2026-02-20T00:00:00Z",
                    },
                    {
                        "observation_id": "obs-a-2",
                        "observed_at_utc": "2026-02-28T00:00:00Z",
                    },
                ],
                "changes": [
                    {
                        "to_observation_id": "obs-a-2",
                        "change_hash": "1" * 64,
                        "changed_fields": ["skills", "seniority"],
                        "field_diffs": {
                            "set_fields": {
                                "skills": {
                                    "added": ["Threat Modeling", "Systems Design", "Python"],
                                    "removed": [],
                                }
                            },
                            "numeric_range_fields": {},
                        },
                    }
                ],
            },
            {
                "job_hash": "b" * 64,
                "provider_id": "openai",
                "canonical_url": "https://example.com/jobs/b",
                "observations": [
                    {
                        "observation_id": "obs-b-1",
                        "observed_at_utc": "2026-02-18T00:00:00Z",
                    },
                    {
                        "observation_id": "obs-b-2",
                        "observed_at_utc": "2026-02-25T00:00:00Z",
                    },
                ],
                "changes": [
                    {
                        "to_observation_id": "obs-b-2",
                        "change_hash": "2" * 64,
                        "changed_fields": ["location", "skills"],
                        "field_diffs": {
                            "set_fields": {
                                "skills": {
                                    "added": ["Data Pipelines"],
                                    "removed": ["Python"],
                                }
                            },
                            "numeric_range_fields": {},
                        },
                    }
                ],
            },
            {
                "job_hash": "c" * 64,
                "provider_id": "openai",
                "canonical_url": "https://example.com/jobs/c",
                "observations": [
                    {
                        "observation_id": "obs-c-1",
                        "observed_at_utc": "2026-02-17T00:00:00Z",
                    },
                    {
                        "observation_id": "obs-c-2",
                        "observed_at_utc": "2026-02-26T00:00:00Z",
                    },
                ],
                "changes": [
                    {
                        "to_observation_id": "obs-c-2",
                        "change_hash": "3" * 64,
                        "changed_fields": ["skills"],
                        "field_diffs": {
                            "set_fields": {
                                "skills": {
                                    "added": ["Monitoring"],
                                    "removed": ["Automation"],
                                }
                            },
                            "numeric_range_fields": {},
                        },
                    },
                    {
                        "to_observation_id": "obs-c-2",
                        "change_hash": "4" * 64,
                        "changed_fields": ["skills"],
                        "field_diffs": {
                            "set_fields": {
                                "skills": {
                                    "added": ["OnlyOne"],
                                    "removed": [],
                                }
                            },
                            "numeric_range_fields": {},
                        },
                    },
                ],
            },
        ]
    }


def _ranked_lookup() -> Dict[str, Dict[str, Any]]:
    return {
        "a" * 64: {
            "title": "Staff Security Engineer",
            "company": "Acme",
            "provider": "openai",
            "apply_url": "https://example.com/jobs/a",
            "description": _JD_LEAK_MARKER,
        },
        "b" * 64: {
            "title": "Platform Engineer",
            "company": "Acme",
            "provider": "openai",
            "apply_url": "https://example.com/jobs/b",
            "jd_text": _JD_LEAK_MARKER,
        },
        "c" * 64: {
            "title": "SRE",
            "company": "Beta",
            "provider": "openai",
            "apply_url": "https://example.com/jobs/c",
        },
    }


def test_digest_notable_changes_deterministic_ranking() -> None:
    import scripts.run_daily as run_daily

    reference_dt = datetime(2026, 3, 1, tzinfo=timezone.utc)
    payload_one = run_daily._build_digest_notable_changes_payload(
        reference_dt=reference_dt,
        timeline_payload=_timeline_payload(),
        ranked_lookup=_ranked_lookup(),
        candidate_skill_tokens=["python", "threat modeling"],
        top_n=10,
    )
    payload_two = run_daily._build_digest_notable_changes_payload(
        reference_dt=reference_dt,
        timeline_payload=_timeline_payload(),
        ranked_lookup=_ranked_lookup(),
        candidate_skill_tokens=["python", "threat modeling"],
        top_n=10,
    )

    assert payload_one == payload_two
    last_30 = payload_one["windows"]["last_30_days"]
    hashes = [row["job_hash"] for row in last_30["notable_changes"]]
    assert hashes == ["a" * 64, "b" * 64, "c" * 64]
    assert last_30["notable_changes"][0]["candidate_relevant"] is True
    assert last_30["notable_changes"][1]["candidate_relevant"] is True
    assert last_30["notable_changes"][2]["candidate_relevant"] is False


def test_digest_notable_changes_no_raw_jd_leakage() -> None:
    import scripts.run_daily as run_daily

    payload = run_daily._build_digest_notable_changes_payload(
        reference_dt=datetime(2026, 3, 1, tzinfo=timezone.utc),
        timeline_payload=_timeline_payload(),
        ranked_lookup=_ranked_lookup(),
        candidate_skill_tokens=["python"],
        top_n=10,
    )
    assert_no_forbidden_fields(payload, context="digest_notable_changes")
    serialized = json.dumps(payload, sort_keys=True)
    assert _JD_LEAK_MARKER not in serialized


def test_digest_notable_changes_empty_when_timeline_missing() -> None:
    import scripts.run_daily as run_daily

    payload = run_daily._build_digest_notable_changes_payload(
        reference_dt=datetime(2026, 3, 1, tzinfo=timezone.utc),
        timeline_payload={},
        ranked_lookup={},
        candidate_skill_tokens=[],
        top_n=10,
    )
    assert payload["thresholds"]["min_skill_token_delta"] == 2
    assert payload["windows"]["last_7_days"]["change_event_count"] == 0
    assert payload["windows"]["last_14_days"]["notable_changes"] == []
    assert payload["windows"]["last_30_days"]["aggregates"] == {"providers": [], "companies": []}
