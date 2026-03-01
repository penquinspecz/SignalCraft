#!/usr/bin/env python3
"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable, Dict, List, Sequence

from ji_engine.artifacts.catalog import (
    UI_SAFE_NONSCHEMA_CANONICAL_KEYS,
    UI_SAFE_SCHEMA_SPECS,
    ArtifactCategory,
    assert_no_forbidden_fields,
    canonical_ui_safe_artifact_keys,
    get_artifact_category,
    validate_artifact_payload,
)

try:
    from scripts.schema_validate import resolve_named_schema_path, validate_payload
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from schema_validate import resolve_named_schema_path, validate_payload  # type: ignore

_RUN_ID = "2026-02-21T12:00:00Z"
_CANDIDATE_ID = "local"

_SCHEMA_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_schema(schema_name: str, version: int) -> Dict[str, Any]:
    cache_key = f"{schema_name}.v{version}"
    if cache_key not in _SCHEMA_CACHE:
        path = resolve_named_schema_path(schema_name, version)
        _SCHEMA_CACHE[cache_key] = json.loads(path.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE[cache_key]


def _explanation_payload() -> Dict[str, Any]:
    return {
        "schema_version": "explanation.v1",
        "run_id": _RUN_ID,
        "candidate_id": _CANDIDATE_ID,
        "generated_at": _RUN_ID,
        "scoring_config_sha256": None,
        "top_jobs": [
            {
                "job_hash": "a" * 64,
                "rank": 1,
                "score_total": 91.0,
                "top_positive_signals": [
                    {
                        "name": "boost_relevant",
                        "value": 1,
                        "weight": 5.0,
                        "contribution": 5.0,
                    }
                ],
                "top_negative_signals": [
                    {
                        "name": "penalty_low_level",
                        "value": 1,
                        "weight": -1.0,
                        "contribution": -1.0,
                    }
                ],
                "penalties": [
                    {
                        "name": "penalty_low_level",
                        "amount": 1.0,
                        "reason_code": "penalty_low_level",
                    }
                ],
                "notes": ["Low-level systems penalty applied."],
            }
        ],
        "aggregation": {
            "most_common_penalties": [{"name": "penalty_low_level", "count": 1}],
            "strongest_positive_signals": [{"name": "boost_relevant", "avg_contribution": 5.0}],
            "strongest_negative_signals": [{"name": "penalty_low_level", "avg_contribution": -1.0}],
        },
    }


def _run_summary_payload() -> Dict[str, Any]:
    return {
        "run_summary_schema_version": 1,
        "run_id": _RUN_ID,
        "candidate_id": _CANDIDATE_ID,
        "status": "ok",
        "git_sha": "a" * 40,
        "created_at_utc": _RUN_ID,
        "run_health": {
            "path": "run_health.v1.json",
            "sha256": "b" * 64,
            "status": "ok",
        },
        "run_report": {
            "path": "run_report.json",
            "sha256": "c" * 64,
            "bytes": 128,
        },
        "ranked_outputs": {
            "ranked_json": [],
            "ranked_csv": [],
            "ranked_families_json": [],
            "shortlist_md": [],
        },
        "primary_artifacts": [],
        "costs": {
            "path": "costs.json",
            "sha256": "d" * 64,
            "bytes": 64,
        },
        "scoring_config": {
            "source": "scoring/profiles/cs/defaults.json",
            "config_sha256": "e" * 64,
            "path": "scoring/profiles/cs/defaults.json",
            "provider": "mock",
            "profile": "cs",
        },
        "snapshot_manifest": {
            "applicable": False,
            "path": "snapshots/manifest.json",
            "sha256": None,
        },
        "quicklinks": {
            "run_dir": "state/candidates/local/runs/20260221T120000Z",
            "run_report": "run_report.json",
            "run_health": "run_health.v1.json",
            "costs": "costs.json",
            "provider_availability": "artifacts/provider_availability_v1.json",
            "ranked_json": [],
            "ranked_csv": [],
            "ranked_families_json": [],
            "shortlist_md": [],
        },
    }


def _provider_availability_payload() -> Dict[str, Any]:
    return {
        "provider_availability_schema_version": 1,
        "run_id": _RUN_ID,
        "candidate_id": _CANDIDATE_ID,
        "generated_at_utc": _RUN_ID,
        "provider_registry_sha256": "f" * 64,
        "providers": [
            {
                "provider_id": "mock",
                "mode": "disabled",
                "enabled": False,
                "snapshot_enabled": False,
                "live_enabled": False,
                "availability": "unavailable",
                "reason_code": "provider_disabled",
                "unavailable_reason": "Provider disabled for sanity fixture",
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
                        "policy_snapshot": None,
                        "live_http_status": None,
                        "live_status_code": None,
                    },
                },
            }
        ],
    }


def _digest_payload() -> Dict[str, Any]:
    return {
        "digest_schema_version": 1,
        "run_id": _RUN_ID,
        "candidate_id": _CANDIDATE_ID,
        "generated_at_utc": _RUN_ID,
        "quiet_mode": True,
        "notify": {
            "requested": False,
            "attempted": False,
            "status": "disabled_quiet_mode",
        },
        "source_artifacts": {
            "run_health": {"path": "run_health.v1.json", "sha256": "a" * 64, "bytes": 100},
            "provider_availability": {
                "path": "artifacts/provider_availability_v1.json",
                "sha256": "b" * 64,
                "bytes": 120,
            },
            "explanation": {"path": "artifacts/explanation_v1.json", "sha256": "c" * 64, "bytes": 220},
            "costs": {"path": "costs.json", "sha256": "d" * 64, "bytes": 80},
            "job_timeline": {
                "path": "artifacts/job_timeline_v1.json",
                "sha256": "e" * 64,
                "bytes": 180,
            },
        },
        "current_run": {
            "run_health": {"status": "success", "failed_stage": None, "failure_codes": []},
            "provider_availability": [
                {
                    "provider_id": "mock",
                    "availability": "unavailable",
                    "reason_code": "provider_disabled",
                    "attempts_made": 0,
                }
            ],
            "costs": {
                "ai_estimated_tokens": 123,
                "ai_estimated_cost_usd": "0.001230",
                "embeddings_count": 0,
            },
            "top_jobs": [
                {
                    "job_hash": "e" * 64,
                    "rank": 1,
                    "score_total": 91.0,
                    "title": "Staff Security Engineer",
                    "company": "Acme",
                    "location": "Remote",
                    "apply_url": "https://example.com/jobs/1",
                    "provider": "openai",
                    "profile": "cs",
                    "notes": ["Role relevance boost applied."],
                    "top_positive_signals": [{"name": "boost_relevant", "contribution": 5.0}],
                    "top_negative_signals": [{"name": "penalty_low_level", "contribution": -1.0}],
                }
            ],
        },
        "cadence": {
            "daily": {
                "window_days": 1,
                "window_start_utc": "2026-02-20T12:00:00Z",
                "window_end_utc": _RUN_ID,
                "run_count": 1,
                "run_ids": [_RUN_ID],
                "status_counts": {"success": 1},
                "cost_totals": {
                    "ai_estimated_tokens": 123,
                    "ai_estimated_cost_usd": "0.001230",
                    "embeddings_count": 0,
                },
            },
            "weekly": {
                "window_days": 7,
                "window_start_utc": "2026-02-14T12:00:00Z",
                "window_end_utc": _RUN_ID,
                "run_count": 1,
                "run_ids": [_RUN_ID],
                "status_counts": {"success": 1},
                "cost_totals": {
                    "ai_estimated_tokens": 123,
                    "ai_estimated_cost_usd": "0.001230",
                    "embeddings_count": 0,
                },
            },
        },
        "notable_changes": {
            "thresholds": {"min_skill_token_delta": 2},
            "windows": {
                "last_7_days": {
                    "window_days": 7,
                    "window_start_utc": "2026-02-14T12:00:00Z",
                    "window_end_utc": _RUN_ID,
                    "change_event_count": 1,
                    "notable_changes": [
                        {
                            "job_hash": "e" * 64,
                            "change_hash": "f" * 64,
                            "observed_at_utc": _RUN_ID,
                            "provider_id": "openai",
                            "company": "Acme",
                            "title": "Staff Security Engineer",
                            "canonical_url": "https://example.com/jobs/1",
                            "changed_fields": ["skills"],
                            "skill_tokens_added": ["threat modeling"],
                            "skill_tokens_removed": [],
                            "seniority_shift": False,
                            "location_shift": False,
                            "compensation_shift": False,
                            "candidate_skill_matches": [],
                            "candidate_relevant": False,
                            "significance_score": 2,
                        }
                    ],
                    "aggregates": {
                        "providers": [{"provider_id": "openai", "change_event_count": 1, "job_count": 1}],
                        "companies": [{"company": "Acme", "change_event_count": 1, "job_count": 1}],
                    },
                },
                "last_14_days": {
                    "window_days": 14,
                    "window_start_utc": "2026-02-07T12:00:00Z",
                    "window_end_utc": _RUN_ID,
                    "change_event_count": 1,
                    "notable_changes": [
                        {
                            "job_hash": "e" * 64,
                            "change_hash": "f" * 64,
                            "observed_at_utc": _RUN_ID,
                            "provider_id": "openai",
                            "company": "Acme",
                            "title": "Staff Security Engineer",
                            "canonical_url": "https://example.com/jobs/1",
                            "changed_fields": ["skills"],
                            "skill_tokens_added": ["threat modeling"],
                            "skill_tokens_removed": [],
                            "seniority_shift": False,
                            "location_shift": False,
                            "compensation_shift": False,
                            "candidate_skill_matches": [],
                            "candidate_relevant": False,
                            "significance_score": 2,
                        }
                    ],
                    "aggregates": {
                        "providers": [{"provider_id": "openai", "change_event_count": 1, "job_count": 1}],
                        "companies": [{"company": "Acme", "change_event_count": 1, "job_count": 1}],
                    },
                },
                "last_30_days": {
                    "window_days": 30,
                    "window_start_utc": "2026-01-22T12:00:00Z",
                    "window_end_utc": _RUN_ID,
                    "change_event_count": 1,
                    "notable_changes": [
                        {
                            "job_hash": "e" * 64,
                            "change_hash": "f" * 64,
                            "observed_at_utc": _RUN_ID,
                            "provider_id": "openai",
                            "company": "Acme",
                            "title": "Staff Security Engineer",
                            "canonical_url": "https://example.com/jobs/1",
                            "changed_fields": ["skills"],
                            "skill_tokens_added": ["threat modeling"],
                            "skill_tokens_removed": [],
                            "seniority_shift": False,
                            "location_shift": False,
                            "compensation_shift": False,
                            "candidate_skill_matches": [],
                            "candidate_relevant": False,
                            "significance_score": 2,
                        }
                    ],
                    "aggregates": {
                        "providers": [{"provider_id": "openai", "change_event_count": 1, "job_count": 1}],
                        "companies": [{"company": "Acme", "change_event_count": 1, "job_count": 1}],
                    },
                },
            },
        },
    }


def _ai_insights_payload() -> Dict[str, Any]:
    return {
        "schema_version": "ai_insights_output.v1",
        "status": "ok",
        "reason": "",
        "provider": "openai",
        "profile": "cs",
        "run_id": _RUN_ID,
        "candidate_id": _CANDIDATE_ID,
        "themes": [
            "Theme 1",
            "Theme 2",
            "Theme 3",
        ],
        "actions": [
            {
                "title": "Action 1",
                "rationale": "Rationale 1",
                "supporting_evidence_fields": ["top_titles"],
            },
            {
                "title": "Action 2",
                "rationale": "Rationale 2",
                "supporting_evidence_fields": ["top_companies"],
            },
            {
                "title": "Action 3",
                "rationale": "Rationale 3",
                "supporting_evidence_fields": ["top_locations"],
            },
            {
                "title": "Action 4",
                "rationale": "Rationale 4",
                "supporting_evidence_fields": ["scoring_summary"],
            },
            {
                "title": "Action 5",
                "rationale": "Rationale 5",
                "supporting_evidence_fields": ["most_common_penalties"],
            },
        ],
        "top_roles": [
            {
                "title": "Role A",
                "score": 88,
                "apply_url": "https://example.com/jobs/a",
            }
        ],
        "risks": ["No elevated structured risk detected"],
        "structured_inputs": {
            "job_counts": {
                "new": 1,
                "changed": 0,
                "removed": 0,
                "total": 1,
                "previous_total": 1,
            },
            "top_companies": [{"name": "Acme", "count": 1}],
            "top_titles": [{"name": "Role A", "count": 1}],
            "top_locations": [{"name": "Remote", "count": 1}],
            "top_skills": [{"token": "customer", "count": 1}],
            "scoring_summary": {
                "mean": 88,
                "median": 88,
                "top_n_scores": [88],
            },
            "trend_analysis": [],
            "most_common_penalties": [],
            "strongest_positive_signals": [],
            "strongest_negative_signals": [],
            "score_distribution": {
                "total": 1,
                "buckets": {
                    "gte90": 0,
                    "gte80": 1,
                    "gte70": 0,
                    "gte60": 0,
                    "lt60": 0,
                },
            },
            "top_families": [],
            "diffs": {
                "counts": {
                    "new": 1,
                    "changed": 0,
                    "removed": 0,
                },
                "top_new_titles": ["Role A"],
                "top_changed_titles": [],
                "top_removed_titles": [],
            },
        },
        "metadata": {
            "prompt_version": "weekly_insights_v4",
            "prompt_sha256": "abcd",
            "model": "stub",
            "provider": "openai",
            "profile": "cs",
            "timestamp": _RUN_ID,
            "input_hashes": {"ranked": "abcd"},
            "structured_input_hash": "abcd",
            "cache_key": "abcd",
        },
    }


def _ai_job_briefs_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "reason": "",
        "provider": "openai",
        "profile": "cs",
        "briefs": [
            {
                "job_id": "job-1",
                "apply_url": "https://example.com/jobs/1",
                "title": "Role A",
                "score": 90,
                "why_fit": ["Aligned with role goals."],
                "gaps": ["No major gap."],
                "interview_focus": ["Impact stories."],
                "resume_tweaks": ["Mirror role keywords."],
            }
        ],
        "metadata": {
            "prompt_version": "job_briefs_v1",
            "cache_hits": 0,
        },
    }


def _ai_job_briefs_error_payload() -> Dict[str, Any]:
    return {
        "error": "job_brief_schema_validation_failed",
        "run_id": _RUN_ID,
        "candidate_id": _CANDIDATE_ID,
        "provider": "openai",
        "profile": "cs",
        "schema": "ai_job_brief.v1",
        "schema_errors": ["job_id=job-1: title missing"],
    }


def _validate_ai_job_briefs_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    brief_schema = _load_schema("ai_job_brief", 1)

    required = ("status", "reason", "provider", "profile", "briefs", "metadata")
    for key in required:
        if key not in payload:
            errors.append(f"ai_job_briefs payload missing key: {key}")

    briefs = payload.get("briefs")
    if not isinstance(briefs, list):
        errors.append("ai_job_briefs.briefs must be an array")
        return errors

    for idx, brief in enumerate(briefs):
        if not isinstance(brief, dict):
            errors.append(f"ai_job_briefs.briefs[{idx}] must be an object")
            continue
        brief_errors = validate_payload(brief, brief_schema)
        errors.extend(f"ai_job_briefs.briefs[{idx}] {err}" for err in brief_errors)

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("ai_job_briefs.metadata must be an object")

    return errors


def _validate_ai_job_briefs_error_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required_str = ("error", "run_id", "candidate_id", "provider", "profile", "schema")
    for key in required_str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"ai_job_briefs error payload `{key}` must be non-empty string")

    if payload.get("error") != "job_brief_schema_validation_failed":
        errors.append("ai_job_briefs error payload `error` must be job_brief_schema_validation_failed")
    if payload.get("schema") != "ai_job_brief.v1":
        errors.append("ai_job_briefs error payload `schema` must be ai_job_brief.v1")

    schema_errors = payload.get("schema_errors")
    if not isinstance(schema_errors, list) or not schema_errors:
        errors.append("ai_job_briefs error payload `schema_errors` must be non-empty array")
    else:
        for idx, value in enumerate(schema_errors):
            if not isinstance(value, str) or not value:
                errors.append(f"ai_job_briefs error payload schema_errors[{idx}] must be non-empty string")
    return errors


def artifact_cases() -> Dict[str, Dict[str, Any]]:
    builders: Dict[str, Callable[[], Dict[str, Any]]] = {
        "digest_v1.json": _digest_payload,
        "run_summary.v1.json": _run_summary_payload,
        "provider_availability_v1.json": _provider_availability_payload,
        "explanation_v1.json": _explanation_payload,
        "ai_insights.cs.json": _ai_insights_payload,
        "ai_job_briefs.cs.json": _ai_job_briefs_payload,
        "ai_job_briefs.cs.error.json": _ai_job_briefs_error_payload,
    }
    cases: Dict[str, Dict[str, Any]] = {}
    for artifact_key in canonical_ui_safe_artifact_keys():
        builder = builders.get(artifact_key)
        if builder is None:
            raise RuntimeError(f"No offline sanity fixture builder registered for {artifact_key}")
        cases[artifact_key] = builder()
    return cases


def run_checks() -> Dict[str, Any]:
    errors: List[str] = []
    category_checks_passed = 0
    artifact_model_checks_passed = 0
    schema_checks_passed = 0
    forbidden_field_checks_passed = 0

    cases = artifact_cases()

    for artifact_key, payload in sorted(cases.items()):
        category = get_artifact_category(artifact_key)
        if category != ArtifactCategory.UI_SAFE:
            errors.append(f"{artifact_key}: category mismatch expected={ArtifactCategory.UI_SAFE} actual={category}")
        else:
            category_checks_passed += 1

        try:
            validate_artifact_payload(payload, artifact_key, _RUN_ID, category)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{artifact_key}: validate_artifact_payload failed: {exc}")
        else:
            artifact_model_checks_passed += 1

        try:
            assert_no_forbidden_fields(payload, context=artifact_key)
        except ValueError as exc:
            errors.append(f"{artifact_key}: forbidden field violation: {exc}")
        else:
            forbidden_field_checks_passed += 1

        schema_spec = UI_SAFE_SCHEMA_SPECS.get(artifact_key)
        if schema_spec is not None:
            schema_name, schema_version = schema_spec
            if artifact_key == "ai_job_briefs.cs.json":
                schema_errors = _validate_ai_job_briefs_payload(payload)
            else:
                schema_errors = validate_payload(payload, _load_schema(schema_name, schema_version))
        elif artifact_key in UI_SAFE_NONSCHEMA_CANONICAL_KEYS:
            schema_errors = _validate_ai_job_briefs_error_payload(payload)
        else:
            schema_errors = [f"no schema contract registered for {artifact_key}"]

        if schema_errors:
            errors.extend(f"{artifact_key}: {err}" for err in schema_errors)
        else:
            schema_checks_passed += 1

    return {
        "status": "ok" if not errors else "error",
        "artifacts_checked": len(cases),
        "category_checks_passed": category_checks_passed,
        "artifact_model_checks_passed": artifact_model_checks_passed,
        "schema_checks_passed": schema_checks_passed,
        "forbidden_field_checks_passed": forbidden_field_checks_passed,
        "errors": errors,
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic dashboard offline sanity checks.")
    ap.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = ap.parse_args(argv)

    summary = run_checks()

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print("dashboard_offline_sanity")
        print(f"status={summary['status']}")
        print(f"artifacts_checked={summary['artifacts_checked']}")
        print(f"category_checks_passed={summary['category_checks_passed']}")
        print(f"artifact_model_checks_passed={summary['artifact_model_checks_passed']}")
        print(f"schema_checks_passed={summary['schema_checks_passed']}")
        print(f"forbidden_field_checks_passed={summary['forbidden_field_checks_passed']}")
        for err in summary["errors"]:
            print(f"error: {err}")

    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
