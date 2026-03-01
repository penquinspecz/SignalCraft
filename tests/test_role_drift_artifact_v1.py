from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _timeline_payload() -> Dict[str, Any]:
    return {
        "jobs": [
            {
                "job_hash": "a" * 64,
                "provider_id": "openai",
                "observations": [
                    {"observation_id": "obs-a-1", "observed_at_utc": "2026-02-10T00:00:00Z"},
                    {"observation_id": "obs-a-2", "observed_at_utc": "2026-02-28T00:00:00Z"},
                ],
                "changes": [
                    {
                        "from_observation_id": "obs-a-1",
                        "to_observation_id": "obs-a-2",
                        "change_hash": "1" * 64,
                        "changed_fields": ["skills", "seniority"],
                        "field_diffs": {
                            "set_fields": {
                                "skills": {
                                    "added": ["Python", "Kubernetes"],
                                    "removed": ["Flask"],
                                }
                            }
                        },
                    }
                ],
            },
            {
                "job_hash": "b" * 64,
                "provider_id": "openai",
                "observations": [
                    {"observation_id": "obs-b-1", "observed_at_utc": "2026-02-12T00:00:00Z"},
                    {"observation_id": "obs-b-2", "observed_at_utc": "2026-02-26T00:00:00Z"},
                ],
                "changes": [
                    {
                        "from_observation_id": "obs-b-1",
                        "to_observation_id": "obs-b-2",
                        "change_hash": "2" * 64,
                        "changed_fields": ["skills", "location"],
                        "field_diffs": {
                            "set_fields": {
                                "skills": {
                                    "added": ["Go", "Python"],
                                    "removed": [],
                                }
                            }
                        },
                    }
                ],
            },
            {
                "job_hash": "c" * 64,
                "provider_id": "openai",
                "observations": [
                    {"observation_id": "obs-c-1", "observed_at_utc": "2026-02-18T00:00:00Z"},
                    {"observation_id": "obs-c-2", "observed_at_utc": "2026-02-27T00:00:00Z"},
                ],
                "changes": [
                    {
                        "from_observation_id": "obs-c-1",
                        "to_observation_id": "obs-c-2",
                        "change_hash": "3" * 64,
                        "changed_fields": ["skills"],
                        "field_diffs": {
                            "set_fields": {
                                "skills": {
                                    "added": ["Terraform"],
                                    "removed": ["Ansible"],
                                }
                            }
                        },
                    }
                ],
            },
        ]
    }


def _ranked_lookup() -> Dict[str, Dict[str, Any]]:
    return {
        "a" * 64: {"company": "Acme", "provider": "openai", "title": "Staff Platform Engineer"},
        "b" * 64: {"company": "Acme", "provider": "openai", "title": "Senior Platform Engineer"},
        "c" * 64: {"company": "Beta", "provider": "openai", "title": "SRE"},
    }


def test_role_drift_payload_is_deterministic() -> None:
    import scripts.run_daily as run_daily

    reference_dt = datetime(2026, 3, 1, tzinfo=timezone.utc)
    payload_one = run_daily._build_role_drift_payload(
        run_id="2026-03-01T00:00:00Z",
        candidate_id="local",
        reference_dt=reference_dt,
        timeline_path=Path("artifacts/job_timeline_v1.json"),
        timeline_payload=_timeline_payload(),
        ranked_lookup=_ranked_lookup(),
    )
    payload_two = run_daily._build_role_drift_payload(
        run_id="2026-03-01T00:00:00Z",
        candidate_id="local",
        reference_dt=reference_dt,
        timeline_path=Path("artifacts/job_timeline_v1.json"),
        timeline_payload=_timeline_payload(),
        ranked_lookup=_ranked_lookup(),
    )

    assert payload_one == payload_two
    companies = payload_one["windows"]["last_30_days"]["companies"]
    assert [row["company_key"] for row in companies] == ["openai::acme", "openai::beta"]


def test_role_drift_aggregation_from_timeline_fixture() -> None:
    import scripts.run_daily as run_daily

    payload = run_daily._build_role_drift_payload(
        run_id="2026-03-01T00:00:00Z",
        candidate_id="local",
        reference_dt=datetime(2026, 3, 1, tzinfo=timezone.utc),
        timeline_path=Path("artifacts/job_timeline_v1.json"),
        timeline_payload=_timeline_payload(),
        ranked_lookup=_ranked_lookup(),
    )
    last_30 = payload["windows"]["last_30_days"]["companies"]
    acme = next(row for row in last_30 if row["company_key"] == "openai::acme")
    assert acme["change_event_count"] == 2
    assert acme["job_count"] == 2
    assert acme["skills_rising"][:2] == [
        {"token": "python", "count": 2},
        {"token": "go", "count": 1},
    ]
    assert acme["skills_falling"] == [{"token": "flask", "count": 1}]
    assert acme["seniority_shift_count"] == 1
    assert acme["location_shift_count"] == 1
    assert acme["seniority_shift_roles"] == ["Staff Platform Engineer"]
    assert acme["location_shift_roles"] == ["Senior Platform Engineer"]
