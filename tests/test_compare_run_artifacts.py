from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import scripts.compare_run_artifacts as compare_run_artifacts


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _build_run_health(run_id: str) -> Dict[str, Any]:
    phase = {"status": "success", "duration_sec": 0.0, "failure_codes": []}
    return {
        "run_health_schema_version": 1,
        "run_id": run_id,
        "candidate_id": "local",
        "status": "success",
        "timestamps": {"started_at": "2026-02-17T00:00:00Z", "ended_at": "2026-02-17T00:00:01Z"},
        "durations": {"total_sec": 1.0},
        "failed_stage": None,
        "failure_codes": [],
        "phases": {
            "snapshot_fetch": dict(phase),
            "normalize": dict(phase),
            "score": dict(phase),
            "publish": dict(phase),
            "ai_sidecar": dict(phase),
        },
        "logs": {"platform": "test-only"},
        "proof_bundle_path": "proofs/bundle.tar.gz",
    }


def _build_provider_availability(run_id: str) -> Dict[str, Any]:
    return {
        "provider_availability_schema_version": 1,
        "run_id": run_id,
        "candidate_id": "local",
        "generated_at_utc": "2026-02-17T00:00:01Z",
        "provider_registry_sha256": "registry-sha-1",
        "providers": [
            {
                "provider_id": "openai",
                "mode": "snapshot",
                "enabled": True,
                "snapshot_enabled": True,
                "live_enabled": False,
                "availability": "available",
                "reason_code": "snapshot_available",
                "unavailable_reason": None,
                "attempts_made": 0,
                "policy": {
                    "robots": {
                        "url": None,
                        "fetched": None,
                        "status_code": None,
                        "allowed": None,
                        "reason": None,
                        "user_agent": None,
                    },
                    "network_shield": {
                        "allowlist_allowed": None,
                        "robots_final_allowed": None,
                        "live_error_reason": None,
                        "live_error_type": None,
                    },
                    "canonical_url_policy": {
                        "policy_snapshot": {},
                        "live_http_status": None,
                        "live_status_code": None,
                    },
                },
            }
        ],
    }


def _build_run_summary(run_id: str) -> Dict[str, Any]:
    return {
        "run_summary_schema_version": 1,
        "run_id": run_id,
        "candidate_id": "local",
        "status": "success",
        "git_sha": "abc123",
        "created_at_utc": "2026-02-17T00:00:01Z",
        "run_health": {"path": "run_health.v1.json", "sha256": "h", "status": "success"},
        "run_report": {"path": "run_report.json", "sha256": "r", "bytes": 100},
        "ranked_outputs": {
            "ranked_json": [
                {
                    "provider": "openai",
                    "profile": "cs",
                    "path": "artifacts/openai_ranked_jobs.cs.json",
                    "sha256": "j",
                    "bytes": 10,
                }
            ],
            "ranked_csv": [
                {
                    "provider": "openai",
                    "profile": "cs",
                    "path": "artifacts/openai_ranked_jobs.cs.csv",
                    "sha256": "c",
                    "bytes": 10,
                }
            ],
            "ranked_families_json": [
                {
                    "provider": "openai",
                    "profile": "cs",
                    "path": "artifacts/openai_ranked_families.cs.json",
                    "sha256": "f",
                    "bytes": 10,
                }
            ],
            "shortlist_md": [],
        },
        "primary_artifacts": [
            {
                "artifact_key": "ranked_json",
                "provider": "openai",
                "profile": "cs",
                "path": "artifacts/openai_ranked_jobs.cs.json",
                "sha256": "j",
                "bytes": 10,
            },
            {
                "artifact_key": "ranked_csv",
                "provider": "openai",
                "profile": "cs",
                "path": "artifacts/openai_ranked_jobs.cs.csv",
                "sha256": "c",
                "bytes": 10,
            },
            {
                "artifact_key": "shortlist_md",
                "provider": "openai",
                "profile": "cs",
                "path": "artifacts/openai_shortlist.cs.md",
                "sha256": "s",
                "bytes": 10,
            },
            {
                "artifact_key": "provider_availability",
                "provider": "openai",
                "profile": "cs",
                "path": "artifacts/provider_availability_v1.json",
                "sha256": "p",
                "bytes": 10,
            },
        ],
        "costs": {"path": "costs.v1.json", "sha256": "z", "bytes": 10},
        "scoring_config": {
            "source": "scoring_v1/openai/scoring.cs.yaml",
            "config_sha256": "scoring-sha-1",
            "path": "scoring/scoring.cs.yaml",
            "provider": "openai",
            "profile": "cs",
        },
        "snapshot_manifest": {"applicable": True, "path": "data/openai_snapshots/index.html", "sha256": "snap-sha-1"},
        "quicklinks": {
            "run_dir": "/tmp/left",
            "run_report": "/tmp/left/run_report.json",
            "run_health": "/tmp/left/run_health.v1.json",
            "costs": "/tmp/left/costs.v1.json",
            "provider_availability": "/tmp/left/artifacts/provider_availability_v1.json",
            "ranked_json": ["/tmp/left/artifacts/openai_ranked_jobs.cs.json"],
            "ranked_csv": ["/tmp/left/artifacts/openai_ranked_jobs.cs.csv"],
            "ranked_families_json": ["/tmp/left/artifacts/openai_ranked_families.cs.json"],
            "shortlist_md": ["/tmp/left/artifacts/openai_shortlist.cs.md"],
        },
    }


def _write_ranked_files(run_dir: Path, *, rows: List[Dict[str, Any]]) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "openai_ranked_jobs.cs.json").write_text(json.dumps(rows, sort_keys=True), encoding="utf-8")
    csv_lines = ["job_id,score"]
    csv_lines.extend(f"{row['job_id']},{row['score']}" for row in rows)
    (artifacts / "openai_ranked_jobs.cs.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")
    (artifacts / "openai_ranked_families.cs.json").write_text(
        json.dumps([{"family": "software", "count": len(rows)}], sort_keys=True), encoding="utf-8"
    )
    (artifacts / "provider_availability_v1.json").write_text("{}", encoding="utf-8")
    (artifacts / "openai_shortlist.cs.md").write_text("# shortlist\n", encoding="utf-8")


def _write_run(run_dir: Path, *, run_id: str, rows: List[Dict[str, Any]]) -> None:
    _write_ranked_files(run_dir, rows=rows)
    _write_json(run_dir / "run_summary.v1.json", _build_run_summary(run_id))
    _write_json(run_dir / "run_health.v1.json", _build_run_health(run_id))
    _write_json(run_dir / "artifacts" / "provider_availability_v1.json", _build_provider_availability(run_id))


def test_compare_run_artifacts_passes_when_only_timestamp_and_environment_metadata_differ(
    tmp_path: Path, capsys
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    rows = [{"job_id": "a", "score": 100}, {"job_id": "b", "score": 90}]

    _write_run(left, run_id="20260217T000000Z", rows=rows)
    _write_run(right, run_id="20260217T000000Z", rows=rows)

    right_summary = json.loads((right / "run_summary.v1.json").read_text(encoding="utf-8"))
    right_summary["created_at_utc"] = "2026-02-17T08:00:00Z"
    right_summary["git_sha"] = "def456"
    right_summary["quicklinks"]["run_dir"] = "/tmp/right"
    _write_json(right / "run_summary.v1.json", right_summary)

    right_health = json.loads((right / "run_health.v1.json").read_text(encoding="utf-8"))
    right_health["timestamps"]["started_at"] = "2026-02-17T08:00:00Z"
    right_health["durations"]["total_sec"] = 7.5
    _write_json(right / "run_health.v1.json", right_health)

    right_availability = json.loads((right / "artifacts" / "provider_availability_v1.json").read_text(encoding="utf-8"))
    right_availability["generated_at_utc"] = "2026-02-17T08:00:01Z"
    _write_json(right / "artifacts" / "provider_availability_v1.json", right_availability)

    rc = compare_run_artifacts.main([str(left), str(right), "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PASS: dual-run deterministic comparison matched" in out


def test_compare_run_artifacts_fails_when_ranked_job_order_differs(tmp_path: Path, capsys) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left_rows = [{"job_id": "a", "score": 100}, {"job_id": "b", "score": 90}]
    right_rows = [{"job_id": "b", "score": 90}, {"job_id": "a", "score": 100}]
    _write_run(left, run_id="20260217T000000Z", rows=left_rows)
    _write_run(right, run_id="20260217T000000Z", rows=right_rows)

    rc = compare_run_artifacts.main([str(left), str(right), "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "job order differs" in out


def test_compare_run_artifacts_fails_when_ranked_scores_differ(tmp_path: Path, capsys) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    _write_run(left, run_id="20260217T000000Z", rows=[{"job_id": "a", "score": 100}])
    _write_run(right, run_id="20260217T000000Z", rows=[{"job_id": "a", "score": 50}])

    rc = compare_run_artifacts.main([str(left), str(right), "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "scores differ" in out


def test_compare_run_artifacts_fails_when_artifact_schema_differs(tmp_path: Path, capsys) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    rows = [{"job_id": "a", "score": 100}]
    _write_run(left, run_id="20260217T000000Z", rows=rows)
    _write_run(right, run_id="20260217T000000Z", rows=rows)

    right_health = json.loads((right / "run_health.v1.json").read_text(encoding="utf-8"))
    right_health["run_health_schema_version"] = 2
    _write_json(right / "run_health.v1.json", right_health)

    rc = compare_run_artifacts.main([str(left), str(right), "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "run_health_schema_version=2 expected=1" in out
