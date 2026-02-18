#!/usr/bin/env python3
from __future__ import annotations

try:
    import _bootstrap  # type: ignore
except ModuleNotFoundError:
    from scripts import _bootstrap  # noqa: F401

import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from scripts.schema_validate import resolve_named_schema_path, validate_payload

CANONICAL_JSON_KWARGS = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")}
VOLATILE_VALUE_KEYS = {
    "created_at",
    "created_at_utc",
    "ended_at",
    "fetched_at",
    "generated_at_utc",
    "run_started_at",
    "scored_at",
    "scraped_at",
    "started_at",
    "timestamp",
    "updated_at",
}
RUN_SUMMARY_DROP_KEYS = {"created_at_utc", "git_sha", "quicklinks"}
RUN_HEALTH_DROP_KEYS = {"timestamps", "durations", "logs", "proof_bundle_path"}
PROVIDER_AVAILABILITY_DROP_KEYS = {"generated_at_utc"}
JOB_ID_FIELDS = ("job_id", "id", "apply_url", "detail_url", "url")
SCORE_FIELDS = ("score", "total_score", "blended_score", "semantic_score")


def _canonical(value: Any) -> str:
    return json.dumps(value, **CANONICAL_JSON_KWARGS)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_recursive(value: Any, *, drop_run_id: bool) -> Any:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, child in value.items():
            if key in VOLATILE_VALUE_KEYS:
                continue
            if drop_run_id and key == "run_id":
                continue
            out[key] = _normalize_recursive(child, drop_run_id=drop_run_id)
        return out
    if isinstance(value, list):
        return [_normalize_recursive(item, drop_run_id=drop_run_id) for item in value]
    return value


def _normalize_run_summary(payload: Dict[str, Any], *, drop_run_id: bool) -> Dict[str, Any]:
    value = deepcopy(payload)
    for key in RUN_SUMMARY_DROP_KEYS:
        value.pop(key, None)
    if drop_run_id:
        value.pop("run_id", None)
    for section in ("run_health", "run_report", "costs", "snapshot_manifest", "scoring_config"):
        node = value.get(section)
        if isinstance(node, dict):
            node.pop("path", None)
    ranked_outputs = value.get("ranked_outputs")
    if isinstance(ranked_outputs, dict):
        for kind in ("ranked_json", "ranked_csv", "ranked_families_json", "shortlist_md"):
            entries = ranked_outputs.get(kind)
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        entry.pop("path", None)
    primary = value.get("primary_artifacts")
    if isinstance(primary, list):
        for entry in primary:
            if isinstance(entry, dict):
                entry.pop("path", None)
    return _normalize_recursive(value, drop_run_id=drop_run_id)


def _normalize_run_health(payload: Dict[str, Any], *, drop_run_id: bool) -> Dict[str, Any]:
    value = deepcopy(payload)
    for key in RUN_HEALTH_DROP_KEYS:
        value.pop(key, None)
    if drop_run_id:
        value.pop("run_id", None)
    return _normalize_recursive(value, drop_run_id=drop_run_id)


def _normalize_provider_availability(payload: Dict[str, Any], *, drop_run_id: bool) -> Dict[str, Any]:
    value = deepcopy(payload)
    for key in PROVIDER_AVAILABILITY_DROP_KEYS:
        value.pop(key, None)
    if drop_run_id:
        value.pop("run_id", None)
    return _normalize_recursive(value, drop_run_id=drop_run_id)


def _validate_schema(payload: Dict[str, Any], schema_name: str, version: int) -> List[str]:
    schema = _load_json(resolve_named_schema_path(schema_name, version))
    return validate_payload(payload, schema)


def _assert_schema_version(
    payload: Dict[str, Any], field: str, expected: int, *, label: str, issues: List[str]
) -> Optional[int]:
    value = payload.get(field)
    if not isinstance(value, int):
        issues.append(f"{label}: missing or invalid {field}")
        return None
    if value != expected:
        issues.append(f"{label}: {field}={value} expected={expected}")
    return value


def _resolve_relative(path_str: str, run_dir: Path, repo_root: Path) -> Path:
    path = Path(path_str)
    candidates: List[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.extend((run_dir / path, repo_root / path))
        if len(path.parts) == 1:
            candidates.append(run_dir / "artifacts" / path)
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved
    attempted = ", ".join(str(c.resolve()) for c in candidates) or "(none)"
    raise FileNotFoundError(f"could not resolve artifact path '{path_str}'. tried: {attempted}")


def _require_object(payload: Any, *, label: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label}: expected JSON object")
    return payload


def _extract_job_list(payload: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return list(payload)
    if isinstance(payload, dict):
        for key in ("jobs", "ranked_jobs", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return list(value)
    return None


def _job_identity(job: Dict[str, Any]) -> str:
    for key in JOB_ID_FIELDS:
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _canonical(job)


def _find_score_fields(rows: Iterable[Dict[str, Any]]) -> List[str]:
    fields: List[str] = []
    for candidate in SCORE_FIELDS:
        if any(candidate in row for row in rows):
            fields.append(candidate)
    return fields


def _compare_ranked_json(left_path: Path, right_path: Path, *, label: str, issues: List[str]) -> None:
    left_payload = _load_json(left_path)
    right_payload = _load_json(right_path)
    left_jobs = _extract_job_list(left_payload)
    right_jobs = _extract_job_list(right_payload)
    if left_jobs is None or right_jobs is None:
        issues.append(f"{label}: ranked JSON schema differs (cannot extract comparable job lists)")
        return
    if len(left_jobs) != len(right_jobs):
        issues.append(f"{label}: ranked JSON length differs ({len(left_jobs)} != {len(right_jobs)})")
        return
    score_fields = _find_score_fields(left_jobs + right_jobs)
    for idx, (left_job, right_job) in enumerate(zip(left_jobs, right_jobs, strict=True)):
        left_id = _job_identity(left_job)
        right_id = _job_identity(right_job)
        if left_id != right_id:
            issues.append(f"{label}: job order differs at index {idx} ({left_id!r} != {right_id!r})")
            return
        for score_key in score_fields:
            if left_job.get(score_key) != right_job.get(score_key):
                issues.append(
                    f"{label}: scores differ at index {idx} field={score_key} "
                    f"left={left_job.get(score_key)!r} right={right_job.get(score_key)!r}"
                )
                return
        left_norm = _normalize_recursive(left_job, drop_run_id=True)
        right_norm = _normalize_recursive(right_job, drop_run_id=True)
        if left_norm != right_norm:
            issues.append(f"{label}: ranked JSON row differs at index {idx}")
            return


def _load_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return headers, rows


def _pick_id_column(headers: List[str]) -> Optional[str]:
    for field in JOB_ID_FIELDS:
        if field in headers:
            return field
    return None


def _normalize_csv_row(row: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in row.items() if k not in VOLATILE_VALUE_KEYS and k != "run_id"}


def _compare_ranked_csv(left_path: Path, right_path: Path, *, label: str, issues: List[str]) -> None:
    left_headers, left_rows = _load_csv_rows(left_path)
    right_headers, right_rows = _load_csv_rows(right_path)
    if left_headers != right_headers:
        issues.append(f"{label}: ranked CSV schema differs (header mismatch)")
        return
    if len(left_rows) != len(right_rows):
        issues.append(f"{label}: ranked CSV length differs ({len(left_rows)} != {len(right_rows)})")
        return
    id_col = _pick_id_column(left_headers)
    score_cols = [field for field in SCORE_FIELDS if field in left_headers]
    for idx, (left_row, right_row) in enumerate(zip(left_rows, right_rows, strict=True)):
        if id_col and left_row.get(id_col) != right_row.get(id_col):
            issues.append(
                f"{label}: job order differs at index {idx} ({left_row.get(id_col)!r} != {right_row.get(id_col)!r})"
            )
            return
        for score_col in score_cols:
            if left_row.get(score_col) != right_row.get(score_col):
                issues.append(
                    f"{label}: scores differ at index {idx} field={score_col} "
                    f"left={left_row.get(score_col)!r} right={right_row.get(score_col)!r}"
                )
                return
        if _normalize_csv_row(left_row) != _normalize_csv_row(right_row):
            issues.append(f"{label}: ranked CSV row differs at index {idx}")
            return


def _compare_ranked_families_json(left_path: Path, right_path: Path, *, label: str, issues: List[str]) -> None:
    left_payload = _normalize_recursive(_load_json(left_path), drop_run_id=True)
    right_payload = _normalize_recursive(_load_json(right_path), drop_run_id=True)
    if type(left_payload) is not type(right_payload):
        issues.append(f"{label}: ranked families schema differs (JSON type mismatch)")
        return
    if left_payload != right_payload:
        issues.append(f"{label}: ranked families differ")


def _collect_ranked_paths(summary: Dict[str, Any], run_dir: Path, repo_root: Path, *, side: str) -> Dict[str, Path]:
    ranked_outputs = summary.get("ranked_outputs")
    if not isinstance(ranked_outputs, dict):
        raise ValueError(f"{side}: run_summary.ranked_outputs missing or invalid")
    out: Dict[str, Path] = {}
    for kind in ("ranked_json", "ranked_csv", "ranked_families_json"):
        entries = ranked_outputs.get(kind)
        if not isinstance(entries, list):
            raise ValueError(f"{side}: run_summary.ranked_outputs.{kind} must be a list")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"{side}: run_summary.ranked_outputs.{kind} entry must be an object")
            provider = entry.get("provider")
            profile = entry.get("profile")
            path = entry.get("path")
            if not isinstance(provider, str) or not isinstance(profile, str) or not isinstance(path, str):
                raise ValueError(f"{side}: ranked output entry missing provider/profile/path")
            key = f"{kind}:{provider}:{profile}"
            if key in out:
                raise ValueError(f"{side}: duplicate ranked output entry for {key}")
            out[key] = _resolve_relative(path, run_dir, repo_root)
    return out


def _read_run_artifacts(run_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    summary = _require_object(_load_json(run_dir / "run_summary.v1.json"), label=f"{run_dir}/run_summary.v1.json")
    health = _require_object(_load_json(run_dir / "run_health.v1.json"), label=f"{run_dir}/run_health.v1.json")
    availability = _require_object(
        _load_json(run_dir / "artifacts" / "provider_availability_v1.json"),
        label=f"{run_dir}/artifacts/provider_availability_v1.json",
    )
    return summary, health, availability


def _contract_check(
    left_summary: Dict[str, Any],
    left_health: Dict[str, Any],
    left_availability: Dict[str, Any],
    right_summary: Dict[str, Any],
    right_health: Dict[str, Any],
    right_availability: Dict[str, Any],
    *,
    allow_run_id_drift: bool,
    issues: List[str],
) -> None:
    left_candidate = left_summary.get("candidate_id")
    right_candidate = right_summary.get("candidate_id")
    if left_candidate != right_candidate:
        issues.append(f"contract: candidate namespace differs ({left_candidate!r} != {right_candidate!r})")

    for side, summary, health, availability in (
        ("left", left_summary, left_health, left_availability),
        ("right", right_summary, right_health, right_availability),
    ):
        sid = summary.get("run_id")
        hid = health.get("run_id")
        aid = availability.get("run_id")
        if sid != hid or sid != aid:
            issues.append(f"contract: {side} run_id inconsistent across artifacts ({sid!r}, {hid!r}, {aid!r})")

    if not allow_run_id_drift and left_summary.get("run_id") != right_summary.get("run_id"):
        issues.append(
            f"contract: run_id differs ({left_summary.get('run_id')!r} != {right_summary.get('run_id')!r}); "
            "use --allow-run-id-drift for deterministic equivalent runs"
        )

    left_snapshot = left_summary.get("snapshot_manifest")
    right_snapshot = right_summary.get("snapshot_manifest")
    if not isinstance(left_snapshot, dict) or not isinstance(right_snapshot, dict):
        issues.append("contract: snapshot_manifest missing in run_summary")
    else:
        left_pair = (left_snapshot.get("applicable"), left_snapshot.get("sha256"))
        right_pair = (right_snapshot.get("applicable"), right_snapshot.get("sha256"))
        if left_pair != right_pair:
            issues.append(f"contract: snapshot set differs ({left_pair!r} != {right_pair!r})")

    left_scoring = left_summary.get("scoring_config")
    right_scoring = right_summary.get("scoring_config")
    if not isinstance(left_scoring, dict) or not isinstance(right_scoring, dict):
        issues.append("contract: scoring_config missing in run_summary")
    else:
        left_tuple = (
            left_scoring.get("source"),
            left_scoring.get("config_sha256"),
            left_scoring.get("provider"),
            left_scoring.get("profile"),
        )
        right_tuple = (
            right_scoring.get("source"),
            right_scoring.get("config_sha256"),
            right_scoring.get("provider"),
            right_scoring.get("profile"),
        )
        if left_tuple != right_tuple:
            issues.append(f"contract: scoring config differs ({left_tuple!r} != {right_tuple!r})")

    left_registry = left_availability.get("provider_registry_sha256")
    right_registry = right_availability.get("provider_registry_sha256")
    if left_registry != right_registry:
        issues.append(f"contract: provider registry differs ({left_registry!r} != {right_registry!r})")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministically compare run artifacts across environments.")
    parser.add_argument("left_run_dir", help="Left run directory (for example AWS run path).")
    parser.add_argument("right_run_dir", help="Right run directory (for example k3s on-prem run path).")
    parser.add_argument(
        "--allow-run-id-drift",
        action="store_true",
        help="Allow deterministic-equivalent run IDs to differ between left and right.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root used for resolving relative ranked artifact paths (default: current directory).",
    )
    args = parser.parse_args(argv)

    left_run_dir = Path(args.left_run_dir).resolve()
    right_run_dir = Path(args.right_run_dir).resolve()
    repo_root = Path(args.repo_root).resolve()

    issues: List[str] = []
    try:
        left_summary, left_health, left_availability = _read_run_artifacts(left_run_dir)
        right_summary, right_health, right_availability = _read_run_artifacts(right_run_dir)
    except Exception as exc:
        print(f"FAIL: unable to load required artifacts: {exc}")
        return 2

    _assert_schema_version(left_summary, "run_summary_schema_version", 1, label="left run_summary", issues=issues)
    _assert_schema_version(right_summary, "run_summary_schema_version", 1, label="right run_summary", issues=issues)
    _assert_schema_version(left_health, "run_health_schema_version", 1, label="left run_health", issues=issues)
    _assert_schema_version(right_health, "run_health_schema_version", 1, label="right run_health", issues=issues)
    _assert_schema_version(
        left_availability,
        "provider_availability_schema_version",
        1,
        label="left provider_availability",
        issues=issues,
    )
    _assert_schema_version(
        right_availability,
        "provider_availability_schema_version",
        1,
        label="right provider_availability",
        issues=issues,
    )

    left_summary_errors = _validate_schema(left_summary, "run_summary", 1)
    right_summary_errors = _validate_schema(right_summary, "run_summary", 1)
    left_health_errors = _validate_schema(left_health, "run_health", 1)
    right_health_errors = _validate_schema(right_health, "run_health", 1)
    left_availability_errors = _validate_schema(left_availability, "provider_availability", 1)
    right_availability_errors = _validate_schema(right_availability, "provider_availability", 1)

    if left_summary_errors:
        issues.append(f"left run_summary schema differs: {left_summary_errors[0]}")
    if right_summary_errors:
        issues.append(f"right run_summary schema differs: {right_summary_errors[0]}")
    if left_health_errors:
        issues.append(f"left run_health schema differs: {left_health_errors[0]}")
    if right_health_errors:
        issues.append(f"right run_health schema differs: {right_health_errors[0]}")
    if left_availability_errors:
        issues.append(f"left provider_availability schema differs: {left_availability_errors[0]}")
    if right_availability_errors:
        issues.append(f"right provider_availability schema differs: {right_availability_errors[0]}")

    _contract_check(
        left_summary,
        left_health,
        left_availability,
        right_summary,
        right_health,
        right_availability,
        allow_run_id_drift=args.allow_run_id_drift,
        issues=issues,
    )

    left_summary_norm = _normalize_run_summary(left_summary, drop_run_id=args.allow_run_id_drift)
    right_summary_norm = _normalize_run_summary(right_summary, drop_run_id=args.allow_run_id_drift)
    if _canonical(left_summary_norm) != _canonical(right_summary_norm):
        issues.append("run_summary differs after ignoring timestamps and environment metadata")

    left_health_norm = _normalize_run_health(left_health, drop_run_id=args.allow_run_id_drift)
    right_health_norm = _normalize_run_health(right_health, drop_run_id=args.allow_run_id_drift)
    if _canonical(left_health_norm) != _canonical(right_health_norm):
        issues.append("run_health differs after ignoring timestamps and environment metadata")

    left_availability_norm = _normalize_provider_availability(left_availability, drop_run_id=args.allow_run_id_drift)
    right_availability_norm = _normalize_provider_availability(right_availability, drop_run_id=args.allow_run_id_drift)
    if _canonical(left_availability_norm) != _canonical(right_availability_norm):
        issues.append("provider_availability differs after ignoring timestamps and environment metadata")

    try:
        left_ranked = _collect_ranked_paths(left_summary, left_run_dir, repo_root, side="left")
        right_ranked = _collect_ranked_paths(right_summary, right_run_dir, repo_root, side="right")
    except Exception as exc:
        issues.append(f"ranked output resolution failed: {exc}")
        left_ranked = {}
        right_ranked = {}

    if set(left_ranked.keys()) != set(right_ranked.keys()):
        left_only = sorted(set(left_ranked.keys()) - set(right_ranked.keys()))
        right_only = sorted(set(right_ranked.keys()) - set(left_ranked.keys()))
        issues.append(f"ranked output schema differs (left_only={left_only}, right_only={right_only})")
    else:
        for key in sorted(left_ranked.keys()):
            kind = key.split(":", 1)[0]
            left_path = left_ranked[key]
            right_path = right_ranked[key]
            if kind == "ranked_json":
                _compare_ranked_json(left_path, right_path, label=key, issues=issues)
            elif kind == "ranked_csv":
                _compare_ranked_csv(left_path, right_path, label=key, issues=issues)
            elif kind == "ranked_families_json":
                _compare_ranked_families_json(left_path, right_path, label=key, issues=issues)

    if issues:
        print("FAIL: dual-run deterministic comparison failed")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("PASS: dual-run deterministic comparison matched")
    print(f"left_run_dir={left_run_dir}")
    print(f"right_run_dir={right_run_dir}")
    print(f"allow_run_id_drift={args.allow_run_id_drift}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
