from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ji_engine.artifacts.catalog import assert_no_forbidden_fields
from scripts.schema_validate import resolve_named_schema_path, validate_payload

_JD_LEAK_MARKER = "JOB_TIMELINE_JD_LEAK_MARKER_DO_NOT_SERIALIZE"


def _setup_env(monkeypatch: Any, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    output_dir = data_dir / "ashby_cache"
    snapshot_dir = data_dir / "openai_snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "index.html").write_text("<html>snapshot</html>", encoding="utf-8")
    (data_dir / "candidate_profile.json").write_text('{"skills": [], "roles": []}', encoding="utf-8")
    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(state_dir))


def _write_run_fixture(run_daily: Any, run_id: str, jobs: List[Dict[str, Any]]) -> None:
    run_dir = run_daily._run_registry_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    ranked_key = "openai_ranked_jobs.cs.json"
    (run_dir / ranked_key).write_text(json.dumps(jobs), encoding="utf-8")
    (run_dir / "run_report.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "status": "success",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "status": "success",
                "artifacts": {
                    ranked_key: ranked_key,
                },
            }
        ),
        encoding="utf-8",
    )


def _timeline_payload(monkeypatch: Any, tmp_path: Path) -> Tuple[Any, Dict[str, Any], Path]:
    _setup_env(monkeypatch, tmp_path)

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    importlib.reload(config)
    run_daily = importlib.reload(run_daily)

    job_hash = "f" * 64
    run_1 = "2026-01-20T00:00:00Z"
    run_2 = "2026-01-21T00:00:00Z"
    run_3 = "2026-01-22T00:00:00Z"

    _write_run_fixture(
        run_daily,
        run_1,
        [
            {
                "job_hash": job_hash,
                "provider": "openai",
                "title": "Security Engineer",
                "location": "Remote",
                "seniority": "Senior",
                "seniority_tokens": ["senior"],
                "skills_tokens": ["python", "security"],
                "salary_min": 180000,
                "salary_max": 220000,
                "salary_currency": "USD",
                "salary_period": "yearly",
                "apply_url": "https://example.com/jobs/1?utm_source=test",
                "jd_text": f"{_JD_LEAK_MARKER} jd payload",
                "score": 91.0,
            }
        ],
    )
    _write_run_fixture(
        run_daily,
        run_2,
        [
            {
                "job_hash": job_hash,
                "provider": "openai",
                "title": "Staff Security Engineer",
                "location": "Remote (US)",
                "seniority": "Staff",
                "seniority_tokens": ["staff"],
                "skills_tokens": ["python", "security", "threat modeling"],
                "salary_min": 210000,
                "salary_max": 250000,
                "salary_currency": "USD",
                "salary_period": "yearly",
                "apply_url": "https://example.com/jobs/1",
                "description": f"{_JD_LEAK_MARKER} description payload",
                "score": 94.0,
            }
        ],
    )
    _write_run_fixture(
        run_daily,
        run_3,
        [
            {
                "job_hash": job_hash,
                "provider": "openai",
                "title": "Staff Security Engineer",
                "location": "Remote (US)",
                "seniority": "Staff",
                "seniority_tokens": ["staff"],
                "skills_tokens": ["python", "security", "threat modeling"],
                "salary_min": 210000,
                "salary_max": 250000,
                "salary_currency": "USD",
                "salary_period": "yearly",
                "apply_url": "https://example.com/jobs/1",
                "score": 94.0,
            }
        ],
    )

    out_path = run_daily._write_job_timeline_artifact(
        run_id=run_3,
        candidate_id=run_daily.CANDIDATE_ID,
        run_report_path=run_daily._run_registry_dir(run_3) / "run_report.json",
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    return run_daily, payload, out_path


def test_job_timeline_artifact_deterministic(monkeypatch: Any, tmp_path: Path) -> None:
    run_daily, payload, out_path = _timeline_payload(monkeypatch, tmp_path)
    first_bytes = out_path.read_bytes()

    second_path = run_daily._write_job_timeline_artifact(
        run_id="2026-01-22T00:00:00Z",
        candidate_id=run_daily.CANDIDATE_ID,
        run_report_path=run_daily._run_registry_dir("2026-01-22T00:00:00Z") / "run_report.json",
    )
    second_bytes = second_path.read_bytes()

    assert first_bytes == second_bytes
    assert payload["job_timeline_schema_version"] == 1
    assert payload["source_run_count"] == 3
    assert payload["run_id"] == "2026-01-22T00:00:00Z"


def test_job_timeline_artifact_schema_and_no_raw_jd_leak(monkeypatch: Any, tmp_path: Path) -> None:
    _, payload, _ = _timeline_payload(monkeypatch, tmp_path)

    schema = json.loads(resolve_named_schema_path("job_timeline", 1).read_text(encoding="utf-8"))
    errors = validate_payload(payload, schema)
    assert errors == [], f"job timeline schema validation failed: {errors}"

    assert_no_forbidden_fields(payload, context="job_timeline_v1")
    serialized = json.dumps(payload, sort_keys=True)
    assert _JD_LEAK_MARKER not in serialized


def test_job_timeline_field_diff_correctness(monkeypatch: Any, tmp_path: Path) -> None:
    _, payload, _ = _timeline_payload(monkeypatch, tmp_path)

    assert payload["jobs"], "expected at least one timeline"
    timeline = payload["jobs"][0]
    assert timeline["job_hash"] == "f" * 64
    assert timeline["provider_id"] == "openai"
    assert timeline["canonical_url"] == "https://example.com/jobs/1"
    assert len(timeline["observations"]) == 3
    assert len(timeline["changes"]) == 1

    change = timeline["changes"][0]
    assert change["changed_fields"] == [
        "compensation",
        "location",
        "seniority",
        "seniority_tokens",
        "skills",
        "title",
    ]
    assert change["field_diffs"]["string_fields"]["title"] == {
        "from": "Security Engineer",
        "to": "Staff Security Engineer",
    }
    assert change["field_diffs"]["set_fields"]["seniority_tokens"] == {
        "added": ["staff"],
        "removed": ["senior"],
    }
    assert change["field_diffs"]["set_fields"]["skills"] == {
        "added": ["threat modeling"],
        "removed": [],
    }
    compensation_diff = change["field_diffs"]["numeric_range_fields"]["compensation"]
    assert compensation_diff["from"]["min"] == 180000.0
    assert compensation_diff["to"]["min"] == 210000.0
    assert isinstance(change["change_hash"], str)
    assert len(change["change_hash"]) == 64
