"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ji_engine.config import DEFAULT_CANDIDATE_ID, REPO_ROOT, RUN_METADATA_DIR
from ji_engine.run_repository import FileSystemRunRepository, RunRepository
from ji_engine.utils.time import utc_now_iso

try:
    from scripts.schema_validate import resolve_named_schema_path, validate_payload
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from schema_validate import resolve_named_schema_path, validate_payload  # type: ignore

_WINDOW_DAYS = (7, 14, 30)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.-]*")
_TRACKED_DIFF_FIELDS = ("title", "location", "team", "score", "final_score", "role_band")
_SKILL_TOKEN_FIELDS = ("title", "company", "organization", "location", "team", "department", "role_band")
_INPUT_SCHEMA_VERSION = 1
_INPUT_SCHEMA_CACHE: Optional[Dict[str, Any]] = None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Optional[Path]) -> Optional[str]:
    if not path or not path.exists():
        return None
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_jobs(path: Optional[Path]) -> List[Dict[str, Any]]:
    if not path or not path.exists():
        return []
    payload = _read_json(path)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _job_id(job: Dict[str, Any]) -> str:
    value = str(job.get("job_id") or "").strip()
    if value:
        return value
    fallback = str(job.get("apply_url") or job.get("detail_url") or job.get("title") or "").strip()
    return fallback or "missing:unknown"


def _job_title(job: Dict[str, Any]) -> str:
    return str(job.get("title") or "Untitled").strip() or "Untitled"


def _job_company(job: Dict[str, Any]) -> str:
    for key in ("company", "company_name", "organization", "org", "org_name"):
        value = str(job.get(key) or "").strip()
        if value:
            return value
    return "unknown"


def _job_location(job: Dict[str, Any]) -> str:
    for key in ("location", "locationName", "location_norm"):
        value = str(job.get(key) or "").strip()
        if value:
            return value
    return "unknown"


def _job_score(job: Dict[str, Any]) -> int:
    try:
        return int(job.get("score", 0) or 0)
    except Exception:
        return 0


def _stable_role(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _job_title(job),
        "score": _job_score(job),
        "apply_url": str(job.get("apply_url") or ""),
    }


def _top_roles(jobs: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    ordered = sorted(
        jobs,
        key=lambda job: (
            -_job_score(job),
            _job_title(job).lower(),
            str(job.get("apply_url") or "").lower(),
            _job_id(job).lower(),
        ),
    )
    return [_stable_role(job) for job in ordered[:limit]]


def _score_distribution(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    buckets = {"gte90": 0, "gte80": 0, "gte70": 0, "gte60": 0, "lt60": 0}
    for job in jobs:
        score = _job_score(job)
        if score >= 90:
            buckets["gte90"] += 1
        elif score >= 80:
            buckets["gte80"] += 1
        elif score >= 70:
            buckets["gte70"] += 1
        elif score >= 60:
            buckets["gte60"] += 1
        else:
            buckets["lt60"] += 1
    return {"total": len(jobs), "buckets": buckets}


def _median_score(jobs: List[Dict[str, Any]]) -> float:
    scores = sorted(_job_score(job) for job in jobs)
    if not scores:
        return 0.0
    mid = len(scores) // 2
    if len(scores) % 2 == 1:
        return float(scores[mid])
    return float((scores[mid - 1] + scores[mid]) / 2.0)


def _mean_score(jobs: List[Dict[str, Any]]) -> float:
    if not jobs:
        return 0.0
    return round(sum(_job_score(job) for job in jobs) / float(len(jobs)), 3)


def _is_changed(curr: Dict[str, Any], prev: Dict[str, Any]) -> bool:
    for field in _TRACKED_DIFF_FIELDS:
        if str(curr.get(field) or "") != str(prev.get(field) or ""):
            return True
    return False


def _top_counted(items: Dict[str, int], *, key_name: str, limit: int = 8) -> List[Dict[str, Any]]:
    ordered = sorted(items.items(), key=lambda item: (-item[1], item[0].lower()))
    return [{key_name: name, "count": count} for name, count in ordered[:limit]]


def _count_by_field(jobs: List[Dict[str, Any]], field_name: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for job in jobs:
        if field_name == "company":
            value = _job_company(job)
        elif field_name == "location":
            value = _job_location(job)
        else:
            value = _job_title(job)
        counts[value] = counts.get(value, 0) + 1
    return counts


def _top_companies(jobs: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    return _top_counted(_count_by_field(jobs, "company"), key_name="name", limit=limit)


def _top_titles(jobs: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    return _top_counted(_count_by_field(jobs, "title"), key_name="name", limit=limit)


def _top_locations(jobs: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    return _top_counted(_count_by_field(jobs, "location"), key_name="name", limit=limit)


def _structured_skill_tokens(jobs: List[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for job in jobs:
        parts: List[str] = []
        for field in _SKILL_TOKEN_FIELDS:
            value = str(job.get(field) or "").strip()
            if value:
                parts.append(value)
        tokens = _TOKEN_RE.findall(" ".join(parts).lower())
        for token in tokens:
            if len(token) < 2:
                continue
            counts[token] = counts.get(token, 0) + 1
    return _top_counted(counts, key_name="token", limit=limit)


def _top_families(jobs: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for job in jobs:
        family = str(job.get("title_family") or "").strip()
        if not family:
            continue
        counts[family] = counts.get(family, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
    return [{"family": family, "count": count} for family, count in ordered[:limit]]


def _top_recurring_skill_tokens(jobs: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    return _structured_skill_tokens(jobs, limit=limit)


def _diff_summary(curr_jobs: List[Dict[str, Any]], prev_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    curr_map = {_job_id(job): job for job in curr_jobs}
    prev_map = {_job_id(job): job for job in prev_jobs}
    curr_ids = set(curr_map.keys())
    prev_ids = set(prev_map.keys())

    new_ids = sorted(curr_ids - prev_ids)
    removed_ids = sorted(prev_ids - curr_ids)
    changed_ids = sorted(
        [job_id for job_id in (curr_ids & prev_ids) if _is_changed(curr_map[job_id], prev_map[job_id])]
    )
    return {
        "counts": {"new": len(new_ids), "changed": len(changed_ids), "removed": len(removed_ids)},
        "top_new_titles": [_job_title(curr_map[job_id]) for job_id in new_ids[:5]],
        "top_changed_titles": [_job_title(curr_map[job_id]) for job_id in changed_ids[:5]],
        "top_removed_titles": [_job_title(prev_map[job_id]) for job_id in removed_ids[:5]],
    }


def _repository_from_runs_dir(run_metadata_dir: Path) -> RunRepository:
    return FileSystemRunRepository(run_metadata_dir)


def _scoring_summary(curr_jobs: List[Dict[str, Any]], top_n: int = 5) -> Dict[str, Any]:
    scores = sorted((_job_score(job) for job in curr_jobs), reverse=True)
    return {
        "mean": _mean_score(curr_jobs),
        "median": _median_score(curr_jobs),
        "top_n_scores": scores[:top_n],
    }


def _safe_parse_timestamp(value: str) -> Optional[datetime]:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _row_timestamp(row: Dict[str, Any]) -> Optional[datetime]:
    timestamp = row.get("timestamp")
    if isinstance(timestamp, str):
        parsed = _safe_parse_timestamp(timestamp)
        if parsed is not None:
            return parsed
    run_id = row.get("run_id")
    if isinstance(run_id, str):
        return _safe_parse_timestamp(run_id)
    return None


def _row_has_profile(row: Dict[str, Any], profile: str) -> bool:
    providers = row.get("providers")
    if not isinstance(providers, dict):
        return False
    for provider_payload in providers.values():
        if not isinstance(provider_payload, dict):
            continue
        profiles = provider_payload.get("profiles")
        if isinstance(profiles, dict) and profile in profiles:
            return True
    return False


def _resolve_report_path(path_str: str, *, run_dir: Path) -> Path:
    candidate = Path(path_str)
    if candidate.is_absolute():
        return candidate
    if path_str.startswith("state/") or path_str.startswith("data/"):
        return (REPO_ROOT / path_str).resolve()
    return (run_dir / path_str).resolve()


def _load_run_report(
    repo: RunRepository,
    *,
    run_id: str,
    candidate_id: str,
) -> Optional[Dict[str, Any]]:
    run_dir = repo.resolve_run_dir(run_id, candidate_id=candidate_id)
    report_path = run_dir / "run_report.json"
    payload = _read_json(report_path)
    if isinstance(payload, dict):
        return payload
    meta_path = repo.resolve_run_metadata_path(run_id, candidate_id=candidate_id)
    payload = _read_json(meta_path)
    if isinstance(payload, dict):
        return payload
    return None


def _ranked_path_from_report(
    report: Dict[str, Any],
    *,
    provider: str,
    profile: str,
    run_dir: Path,
) -> Optional[Path]:
    outputs_by_provider = report.get("outputs_by_provider")
    if isinstance(outputs_by_provider, dict):
        provider_outputs = outputs_by_provider.get(provider)
        if isinstance(provider_outputs, dict):
            profile_outputs = provider_outputs.get(profile)
            if isinstance(profile_outputs, dict):
                ranked_meta = profile_outputs.get("ranked_json")
                if isinstance(ranked_meta, dict):
                    path_str = ranked_meta.get("path")
                    if isinstance(path_str, str) and path_str.strip():
                        return _resolve_report_path(path_str, run_dir=run_dir)
    outputs_by_profile = report.get("outputs_by_profile")
    if isinstance(outputs_by_profile, dict):
        profile_outputs = outputs_by_profile.get(profile)
        if isinstance(profile_outputs, dict):
            ranked_meta = profile_outputs.get("ranked_json")
            if isinstance(ranked_meta, dict):
                path_str = ranked_meta.get("path")
                if isinstance(path_str, str) and path_str.strip():
                    return _resolve_report_path(path_str, run_dir=run_dir)
    return None


def _delta_counts_from_report(report: Dict[str, Any], *, provider: str, profile: str) -> Dict[str, int]:
    provider_profile = ((report.get("delta_summary") or {}).get("provider_profile") or {}).get(provider) or {}
    profile_entry = provider_profile.get(profile) or {}
    try:
        new_count = int(profile_entry.get("new_job_count", 0) or 0)
        changed_count = int(profile_entry.get("changed_job_count", 0) or 0)
        removed_count = int(profile_entry.get("removed_job_count", 0) or 0)
        ranked_total = int(profile_entry.get("ranked_total", 0) or 0)
    except Exception:
        new_count = 0
        changed_count = 0
        removed_count = 0
        ranked_total = 0
    return {
        "new": max(0, new_count),
        "changed": max(0, changed_count),
        "removed": max(0, removed_count),
        "total": max(0, ranked_total),
    }


def _top_deltas(before: Dict[str, int], after: Dict[str, int], *, limit: int = 5) -> List[Dict[str, Any]]:
    keys = sorted(set(before.keys()) | set(after.keys()))
    deltas: List[Dict[str, Any]] = []
    for key in keys:
        start = int(before.get(key, 0) or 0)
        end = int(after.get(key, 0) or 0)
        delta = end - start
        if delta == 0:
            continue
        deltas.append({"name": key, "start_count": start, "end_count": end, "delta": delta})
    deltas.sort(key=lambda item: (-abs(int(item["delta"])), -int(item["delta"]), str(item["name"]).lower()))
    return deltas[:limit]


def _window_trends(
    *,
    provider: str,
    profile: str,
    run_id: str,
    candidate_id: str,
    run_repository: RunRepository,
) -> List[Dict[str, Any]]:
    rows = run_repository.list_runs(candidate_id=candidate_id, limit=500)
    profiled_rows = [row for row in rows if isinstance(row, dict) and _row_has_profile(row, profile)]

    base_time = _safe_parse_timestamp(run_id)
    if base_time is None:
        base_time = utc_now_iso()
        parsed_now = _safe_parse_timestamp(base_time)
        if parsed_now is None:
            raise RuntimeError(f"utc_now_iso() returned an unparseable timestamp: {base_time!r}")
        base_time = parsed_now

    windows_payload: List[Dict[str, Any]] = []
    for window_days in _WINDOW_DAYS:
        cutoff = base_time - timedelta(days=window_days)
        selected: List[Tuple[datetime, str, Dict[str, Any]]] = []
        for row in profiled_rows:
            row_run_id = str(row.get("run_id") or "").strip()
            if not row_run_id:
                continue
            row_ts = _row_timestamp(row)
            if row_ts is None:
                continue
            if row_ts < cutoff or row_ts > base_time:
                continue
            selected.append((row_ts, row_run_id, row))

        selected.sort(key=lambda item: (item[0], item[1]))

        totals = {"new": 0, "changed": 0, "removed": 0, "total": 0}
        first_companies: Dict[str, int] = {}
        first_titles: Dict[str, int] = {}
        first_locations: Dict[str, int] = {}
        last_companies: Dict[str, int] = {}
        last_titles: Dict[str, int] = {}
        last_locations: Dict[str, int] = {}

        for idx, (_, row_run_id, _) in enumerate(selected):
            report = _load_run_report(run_repository, run_id=row_run_id, candidate_id=candidate_id)
            if not isinstance(report, dict):
                continue
            counts = _delta_counts_from_report(report, provider=provider, profile=profile)
            for key in totals:
                totals[key] += int(counts.get(key, 0))

            run_dir = run_repository.resolve_run_dir(row_run_id, candidate_id=candidate_id)
            ranked_path = _ranked_path_from_report(report, provider=provider, profile=profile, run_dir=run_dir)
            jobs = _load_jobs(ranked_path)
            company_counts = _count_by_field(jobs, "company")
            title_counts = _count_by_field(jobs, "title")
            location_counts = _count_by_field(jobs, "location")

            if idx == 0:
                first_companies = company_counts
                first_titles = title_counts
                first_locations = location_counts
            last_companies = company_counts
            last_titles = title_counts
            last_locations = location_counts

        windows_payload.append(
            {
                "window_days": window_days,
                "runs_considered": len(selected),
                "job_counts": totals,
                "company_growth": _top_deltas(first_companies, last_companies),
                "title_growth": _top_deltas(first_titles, last_titles),
                "location_shift": _top_deltas(first_locations, last_locations),
            }
        )

    return windows_payload


def _load_explanation_summary(
    *,
    run_id: str,
    candidate_id: str,
    run_repository: RunRepository,
) -> Dict[str, Any]:
    try:
        path = run_repository.resolve_run_artifact_path(
            run_id,
            "artifacts/explanation_v1.json",
            candidate_id=candidate_id,
        )
    except Exception:
        return {
            "most_common_penalties": [],
            "strongest_positive_signals": [],
            "strongest_negative_signals": [],
        }
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {
            "most_common_penalties": [],
            "strongest_positive_signals": [],
            "strongest_negative_signals": [],
        }
    aggregation = payload.get("aggregation") if isinstance(payload.get("aggregation"), dict) else {}
    penalties = aggregation.get("most_common_penalties") if isinstance(aggregation, dict) else []
    positives = aggregation.get("strongest_positive_signals") if isinstance(aggregation, dict) else []
    negatives = aggregation.get("strongest_negative_signals") if isinstance(aggregation, dict) else []
    return {
        "most_common_penalties": penalties if isinstance(penalties, list) else [],
        "strongest_positive_signals": positives if isinstance(positives, list) else [],
        "strongest_negative_signals": negatives if isinstance(negatives, list) else [],
    }


def _input_schema() -> Dict[str, Any]:
    global _INPUT_SCHEMA_CACHE
    if _INPUT_SCHEMA_CACHE is None:
        schema_path = resolve_named_schema_path("ai_insights_input", _INPUT_SCHEMA_VERSION)
        _INPUT_SCHEMA_CACHE = json.loads(schema_path.read_text(encoding="utf-8"))
    return _INPUT_SCHEMA_CACHE


def build_weekly_insights_input(
    *,
    provider: str,
    profile: str,
    ranked_path: Path,
    prev_path: Optional[Path],
    ranked_families_path: Optional[Path],
    run_id: str,
    run_metadata_dir: Path = RUN_METADATA_DIR,
    run_repository: Optional[RunRepository] = None,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
) -> Tuple[Path, Dict[str, Any]]:
    repo = run_repository or _repository_from_runs_dir(run_metadata_dir)
    curr_jobs = _load_jobs(ranked_path)
    prev_jobs = _load_jobs(prev_path)
    family_jobs = _load_jobs(ranked_families_path)

    current_median = _median_score(curr_jobs)
    previous_median = _median_score(prev_jobs)
    diffs = _diff_summary(curr_jobs, prev_jobs)
    windows = _window_trends(
        provider=provider,
        profile=profile,
        run_id=run_id,
        candidate_id=candidate_id,
        run_repository=repo,
    )
    explanation = _load_explanation_summary(
        run_id=run_id,
        candidate_id=candidate_id,
        run_repository=repo,
    )

    payload: Dict[str, Any] = {
        "schema_version": "ai_insights_input.v1",
        "generated_at": utc_now_iso(),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "provider": provider,
        "profile": profile,
        "window_days": list(_WINDOW_DAYS),
        "input_hashes": {
            "ranked": _sha256_path(ranked_path),
            "previous": _sha256_path(prev_path),
            "ranked_families": _sha256_path(ranked_families_path),
        },
        "job_counts": {
            "new": int((diffs.get("counts") or {}).get("new", 0) or 0),
            "changed": int((diffs.get("counts") or {}).get("changed", 0) or 0),
            "removed": int((diffs.get("counts") or {}).get("removed", 0) or 0),
            "total": len(curr_jobs),
            "previous_total": len(prev_jobs),
        },
        "top_companies": _top_companies(curr_jobs),
        "top_titles": _top_titles(curr_jobs),
        "top_locations": _top_locations(curr_jobs),
        "top_skills": _structured_skill_tokens(curr_jobs),
        "scoring_summary": _scoring_summary(curr_jobs),
        "trend_analysis": {
            "windows": windows,
            "median_score_trend_delta": {
                "current_median": current_median,
                "previous_median": previous_median,
                "delta": round(current_median - previous_median, 3),
            },
        },
        "most_common_penalties": explanation.get("most_common_penalties") or [],
        "strongest_positive_signals": explanation.get("strongest_positive_signals") or [],
        "strongest_negative_signals": explanation.get("strongest_negative_signals") or [],
        "diffs": diffs,
        "top_roles": _top_roles(curr_jobs),
        "top_families": _top_families(family_jobs if family_jobs else curr_jobs),
        "score_distribution": _score_distribution(curr_jobs),
        "top_recurring_skill_tokens": _top_recurring_skill_tokens(curr_jobs, limit=3),
    }

    schema_errors = validate_payload(payload, _input_schema())
    if schema_errors:
        raise RuntimeError(f"ai_insights_input schema validation failed: {'; '.join(schema_errors)}")

    run_dir = repo.resolve_run_dir(run_id, candidate_id=candidate_id)
    out_path = run_dir / "ai" / f"insights_input.{profile}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path, payload
