"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

import boto3
from botocore.exceptions import ClientError

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, Response
    from pydantic import BaseModel, ConfigDict, Field, ValidationError
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in environments without dashboard extras
    raise RuntimeError("Dashboard dependencies are not installed. Install with: pip install -e '.[dashboard]'") from exc

from ji_engine.artifacts.catalog import (
    DASHBOARD_SCHEMA_VERSION_BY_ARTIFACT_KEY,
    ArtifactCategory,
    assert_no_forbidden_fields,
    get_artifact_category,
    redact_forbidden_fields,
    validate_artifact_payload,
)
from ji_engine.candidates import registry as candidate_registry
from ji_engine.config import (
    DEFAULT_CANDIDATE_ID,
    RUN_METADATA_DIR,
    STATE_DIR,
    candidate_last_success_read_paths,
    candidate_state_paths,
    sanitize_candidate_id,
)
from ji_engine.run_repository import FileSystemRunRepository, RunRepository
from jobintel import aws_runs

app = FastAPI(title="SignalCraft Dashboard API")
logger = logging.getLogger(__name__)
RUN_REPOSITORY: RunRepository = FileSystemRunRepository(RUN_METADATA_DIR)


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.:+-]{1,128}$")
_JOB_HASH_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_DEFAULT_MAX_JSON_BYTES = 2 * 1024 * 1024
_RECENT_CHANGES_WINDOW_DAYS = 30
_MIN_SKILL_TOKEN_DELTA = 2
_MAX_TIMELINE_OBSERVATIONS = 200
_MAX_TIMELINE_CHANGES = 200
_TIMELINE_TOKEN_MAX_ITEMS = 64
_UI_V0_HTML = Path(__file__).with_name("static") / "ui_v0.html"


class _RunIndexSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: Optional[str] = None
    timestamp: Optional[str] = None
    artifacts: Dict[str, str] = Field(default_factory=dict)


class _RunReportSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    semantic_enabled: Optional[bool] = None
    semantic_mode: Optional[str] = None
    outputs_by_provider: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = Field(default_factory=dict)


class _AiInsightsSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    metadata: Dict[str, Any] = Field(default_factory=dict)


class _ProfileFieldsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seniority: Optional[str] = None
    role_archetype: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[List[str]] = None


class _ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = None
    profile_fields: _ProfileFieldsPayload = Field(default_factory=_ProfileFieldsPayload)


class _DashboardJsonError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _max_json_bytes() -> int:
    raw = os.environ.get("JOBINTEL_DASHBOARD_MAX_JSON_BYTES", str(_DEFAULT_MAX_JSON_BYTES)).strip()
    try:
        parsed = int(raw)
    except ValueError:
        logger.warning(
            "Invalid JOBINTEL_DASHBOARD_MAX_JSON_BYTES=%r; using default=%d",
            raw,
            _DEFAULT_MAX_JSON_BYTES,
        )
        return _DEFAULT_MAX_JSON_BYTES
    if parsed <= 0:
        logger.warning(
            "Non-positive JOBINTEL_DASHBOARD_MAX_JSON_BYTES=%d; using default=%d",
            parsed,
            _DEFAULT_MAX_JSON_BYTES,
        )
        return _DEFAULT_MAX_JSON_BYTES
    return parsed


def _validate_schema(payload: Dict[str, Any], schema: Optional[Type[BaseModel]]) -> None:
    if schema is None:
        return
    try:
        schema.model_validate(payload)
    except ValidationError as exc:
        raise _DashboardJsonError("invalid_schema") from exc


def _read_local_json_value(path: Path) -> object:
    if not path.exists():
        raise _DashboardJsonError("not_found")
    max_bytes = _max_json_bytes()
    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        raise _DashboardJsonError("io_error") from exc
    if size_bytes > max_bytes:
        raise _DashboardJsonError("too_large")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _DashboardJsonError("invalid_json") from exc
    except OSError as exc:
        raise _DashboardJsonError("io_error") from exc


def _read_local_json_object(path: Path, *, schema: Optional[Type[BaseModel]] = None) -> Dict[str, Any]:
    payload = _read_local_json_value(path)
    if not isinstance(payload, dict):
        raise _DashboardJsonError("invalid_shape")
    _validate_schema(payload, schema)
    return payload


def _load_optional_json_object(
    path: Path,
    *,
    context: str,
    schema: Optional[Type[BaseModel]] = None,
) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return _read_local_json_object(path, schema=schema)
    except _DashboardJsonError as exc:
        logger.warning("Skipping %s at %s (%s)", context, path, exc.code)
        return None


def _sanitize_candidate_id(candidate_id: str) -> str:
    try:
        return sanitize_candidate_id(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate_id") from exc


def _resolve_candidate_or_active(candidate_id: Optional[str]) -> str:
    if candidate_id is None or not candidate_id.strip():
        try:
            return _sanitize_candidate_id(candidate_registry.get_active_candidate_id())
        except candidate_registry.CandidateValidationError as exc:
            raise HTTPException(status_code=500, detail="Active candidate pointer is invalid") from exc
    return _sanitize_candidate_id(candidate_id)


def _sanitize_run_id(run_id: str) -> str:
    if not isinstance(run_id, str):
        raise HTTPException(status_code=400, detail="Invalid run_id")
    raw = run_id.strip()
    if not _RUN_ID_RE.fullmatch(raw):
        raise HTTPException(status_code=400, detail="Invalid run_id")
    return raw.replace(":", "").replace("-", "").replace(".", "")


def _sanitize_job_hash(job_hash: str) -> str:
    if not isinstance(job_hash, str):
        raise HTTPException(status_code=400, detail="Invalid job_hash")
    raw = job_hash.strip()
    if not _JOB_HASH_RE.fullmatch(raw):
        raise HTTPException(status_code=400, detail="Invalid job_hash")
    return raw


def _ensure_ui_safe(obj: object, context: str = "") -> None:
    """Fail-closed: raise HTTPException 500 if obj contains forbidden JD fields."""
    try:
        assert_no_forbidden_fields(obj, context=context)
    except ValueError as exc:
        try:
            detail = json.loads(str(exc))
        except json.JSONDecodeError:
            detail = {"error": "forbidden_jd_fields", "message": str(exc)}
        raise HTTPException(status_code=500, detail=detail) from exc


def _run_dir(run_id: str, candidate_id: str) -> Path:
    _sanitize_run_id(run_id)
    return RUN_REPOSITORY.resolve_run_dir(run_id, candidate_id=_sanitize_candidate_id(candidate_id))


def _load_index(run_id: str, candidate_id: str) -> Dict[str, Any]:
    safe_candidate = _sanitize_candidate_id(candidate_id)
    index_path = RUN_REPOSITORY.resolve_run_artifact_path(run_id, "index.json", candidate_id=safe_candidate)
    try:
        return _read_local_json_object(index_path, schema=_RunIndexSchema)
    except _DashboardJsonError as exc:
        logger.warning("Failed to load run index at %s (%s)", index_path, exc.code)
        if exc.code == "not_found":
            raise HTTPException(status_code=404, detail="Run not found") from exc
        if exc.code == "too_large":
            raise HTTPException(status_code=413, detail="Run index payload too large") from exc
        if exc.code == "invalid_json":
            raise HTTPException(status_code=500, detail="Run index is invalid JSON") from exc
        raise HTTPException(status_code=500, detail="Run index has invalid shape") from exc


def _load_first_ai_prompt_version(run_id: str, candidate_id: str, index: Dict[str, Any]) -> Optional[str]:
    """Index-backed: resolve ai_insights.*.json from index.artifacts, no directory scan."""
    artifacts = index.get("artifacts") if isinstance(index.get("artifacts"), dict) else {}
    safe_candidate = _sanitize_candidate_id(candidate_id)
    for key in sorted(artifacts.keys()):
        if not (key.startswith("ai_insights.") and key.endswith(".json")):
            continue
        rel = artifacts.get(key)
        if not isinstance(rel, str) or not rel.strip():
            continue
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            continue
        try:
            path = RUN_REPOSITORY.resolve_run_artifact_path(run_id, rel_path.as_posix(), candidate_id=safe_candidate)
        except ValueError:
            continue
        if not path.exists() or not path.is_file():
            continue
        payload = _load_optional_json_object(path, context="AI insights payload", schema=_AiInsightsSchema)
        if not payload:
            continue
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        prompt_version = (metadata or {}).get("prompt_version")
        if isinstance(prompt_version, str) and prompt_version.strip():
            return prompt_version
    return None


def _list_runs(candidate_id: str) -> List[Dict[str, Any]]:
    """List runs via RunRepository (index-first, fallback to filesystem scan)."""
    safe_candidate = _sanitize_candidate_id(candidate_id)
    return RUN_REPOSITORY.list_runs(candidate_id=safe_candidate, limit=200)


def _resolve_artifact_path(run_id: str, candidate_id: str, index: Dict[str, Any], name: str) -> Path:
    if not isinstance(name, str) or not name.strip() or len(name) > 255:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    artifacts = index.get("artifacts") if isinstance(index.get("artifacts"), dict) else {}
    rel = artifacts.get(name)
    if not isinstance(rel, str) or not rel.strip():
        raise HTTPException(status_code=404, detail="Artifact not found")

    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise HTTPException(status_code=500, detail="Artifact mapping is invalid")

    safe_candidate = _sanitize_candidate_id(candidate_id)
    try:
        candidate = RUN_REPOSITORY.resolve_run_artifact_path(
            run_id,
            rel_path.as_posix(),
            candidate_id=safe_candidate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid artifact path") from exc
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return candidate


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".csv":
        return "text/csv"
    if suffix in {".md", ".markdown"}:
        return "text/markdown"
    return "text/plain"


def _schema_version_for_artifact_key(key: str) -> Optional[int]:
    """Derive schema version from artifact key where known. Returns None if unknown."""
    if not key:
        return None
    return DASHBOARD_SCHEMA_VERSION_BY_ARTIFACT_KEY.get(key)


def _s3_bucket() -> str:
    return os.environ.get("JOBINTEL_S3_BUCKET", "").strip()


def _s3_prefix() -> str:
    return os.environ.get("JOBINTEL_S3_PREFIX", "jobintel").strip().strip("/")


def _s3_enabled() -> bool:
    return bool(_s3_bucket())


def _state_last_success_path(candidate_id: str) -> Path:
    safe_candidate = _sanitize_candidate_id(candidate_id)
    for path in candidate_last_success_read_paths(safe_candidate):
        if path.exists():
            return path
    return candidate_last_success_read_paths(safe_candidate)[0]


def _read_local_json(path: Path) -> Dict[str, Any]:
    try:
        return _read_local_json_object(path)
    except _DashboardJsonError as exc:
        logger.warning("Failed to read local JSON at %s (%s)", path, exc.code)
        if exc.code == "not_found":
            raise HTTPException(status_code=404, detail="Local state not found") from exc
        if exc.code == "too_large":
            raise HTTPException(status_code=413, detail="Local state payload too large") from exc
        if exc.code == "invalid_json":
            raise HTTPException(status_code=500, detail="Local state invalid JSON") from exc
        raise HTTPException(status_code=500, detail="Local state has invalid shape") from exc


def _artifact_map(index: Dict[str, Any]) -> Dict[str, str]:
    artifacts = index.get("artifacts")
    if isinstance(artifacts, dict):
        return {str(k): str(v) for k, v in artifacts.items() if isinstance(k, str) and isinstance(v, str)}
    return {}


def _read_artifact_json_value(
    run_id: str,
    candidate_id: str,
    index: Dict[str, Any],
    artifact_name: str,
    *,
    required: bool,
) -> Optional[object]:
    if artifact_name not in _artifact_map(index):
        if required:
            raise HTTPException(status_code=404, detail=f"{artifact_name} not found")
        return None
    path = _resolve_artifact_path(run_id, candidate_id, index, artifact_name)
    try:
        return _read_local_json_value(path)
    except _DashboardJsonError as exc:
        if exc.code == "not_found":
            if required:
                raise HTTPException(status_code=404, detail=f"{artifact_name} not found") from exc
            return None
        if exc.code == "too_large":
            raise HTTPException(status_code=413, detail=f"{artifact_name} payload too large") from exc
        if exc.code == "invalid_json":
            raise HTTPException(status_code=500, detail=f"{artifact_name} invalid JSON") from exc
        raise HTTPException(status_code=500, detail=f"{artifact_name} invalid shape") from exc


def _find_first_artifact_name(index: Dict[str, Any], pattern: str) -> Optional[str]:
    matches = [name for name in sorted(_artifact_map(index).keys()) if fnmatch.fnmatch(name, pattern)]
    return matches[0] if matches else None


def _project_top_jobs(ranked_payload: object, *, top_n: int) -> List[Dict[str, Any]]:
    if not isinstance(ranked_payload, list):
        raise HTTPException(status_code=500, detail="Top jobs artifact invalid shape")
    redacted = redact_forbidden_fields(ranked_payload)
    _ensure_ui_safe(redacted, context="ui_latest.top_jobs")
    if not isinstance(redacted, list):
        raise HTTPException(status_code=500, detail="Top jobs artifact invalid shape")

    allowed_fields = (
        "job_id",
        "job_hash",
        "title",
        "company",
        "location",
        "score",
        "apply_url",
        "provider",
        "profile",
    )
    projected: List[Dict[str, Any]] = []
    for idx, raw in enumerate(redacted):
        if not isinstance(raw, dict):
            continue
        row: Dict[str, Any] = {"rank": idx + 1}
        for field in allowed_fields:
            value = raw.get(field)
            if isinstance(value, (str, int, float, bool)):
                row[field] = value
        projected.append(row)
        if len(projected) >= top_n:
            break
    return projected


def _safe_ui_text(value: Any, *, max_len: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    return normalized[:max_len]


def _safe_ui_tokens(
    raw: Any,
    *,
    max_items: int = _TIMELINE_TOKEN_MAX_ITEMS,
    max_len: int = 64,
    lowercase: bool = False,
) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        token = _safe_ui_text(item, max_len=max_len)
        if not token:
            continue
        out.append(token.lower() if lowercase else token)
    return sorted(set(out))[:max_items]


def _safe_parse_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _extract_compensation_window(
    numeric_fields: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Optional[float]]], Optional[Dict[str, Optional[float]]]]:
    for key in sorted(numeric_fields):
        if not isinstance(key, str):
            continue
        normalized = key.lower()
        if normalized not in {"compensation", "compensation_range"}:
            continue
        payload = numeric_fields.get(key)
        if not isinstance(payload, dict):
            continue
        before = {
            "min": _coerce_float(payload.get("old_min")),
            "max": _coerce_float(payload.get("old_max")),
        }
        after = {
            "min": _coerce_float(payload.get("new_min")),
            "max": _coerce_float(payload.get("new_max")),
        }
        has_before = before["min"] is not None or before["max"] is not None
        has_after = after["min"] is not None or after["max"] is not None
        return (before if has_before else None, after if has_after else None)
    return None, None


def _extract_string_transition(
    string_fields: Dict[str, Any],
    *,
    field_names: Tuple[str, ...],
) -> Tuple[Optional[str], Optional[str]]:
    for key in field_names:
        payload = string_fields.get(key)
        if not isinstance(payload, dict):
            continue
        old_value = _safe_ui_text(payload.get("old"), max_len=120)
        new_value = _safe_ui_text(payload.get("new"), max_len=120)
        if old_value is not None or new_value is not None:
            return old_value, new_value
    return None, None


def _timeline_observation_lookup(job: Dict[str, Any]) -> Dict[str, datetime]:
    observations = job.get("observations")
    if not isinstance(observations, list):
        return {}
    out: Dict[str, datetime] = {}
    for item in observations:
        if not isinstance(item, dict):
            continue
        observation_id = _safe_ui_text(item.get("observation_id"), max_len=128)
        observed_at = _safe_parse_utc(item.get("observed_at_utc"))
        if observation_id and observed_at is not None:
            out[observation_id] = observed_at
    return out


def _project_timeline_observations(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = job.get("observations")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        observation_id = _safe_ui_text(item.get("observation_id"), max_len=128)
        observed_at_dt = _safe_parse_utc(item.get("observed_at_utc"))
        if not observation_id or observed_at_dt is None:
            continue
        out.append(
            {
                "observation_id": observation_id,
                "run_id": _safe_ui_text(item.get("run_id"), max_len=128),
                "observed_at_utc": _utc_iso(observed_at_dt),
            }
        )
    out.sort(key=lambda row: (str(row.get("observed_at_utc") or ""), str(row.get("observation_id") or "")))
    return out[:_MAX_TIMELINE_OBSERVATIONS]


def _project_timeline_change(
    job: Dict[str, Any],
    change: Dict[str, Any],
    *,
    observation_lookup: Dict[str, datetime],
) -> Optional[Dict[str, Any]]:
    to_observation_id = _safe_ui_text(change.get("to_observation_id"), max_len=128)
    if not to_observation_id:
        return None
    observed_dt = observation_lookup.get(to_observation_id)
    if observed_dt is None:
        return None

    changed_fields = _safe_ui_tokens(change.get("changed_fields"), max_items=32, max_len=64, lowercase=True)
    field_diffs = change.get("field_diffs")
    field_diffs = field_diffs if isinstance(field_diffs, dict) else {}
    set_fields = field_diffs.get("set_fields")
    set_fields = set_fields if isinstance(set_fields, dict) else {}
    string_fields = field_diffs.get("string_fields")
    string_fields = string_fields if isinstance(string_fields, dict) else {}
    numeric_fields = field_diffs.get("numeric_range_fields")
    numeric_fields = numeric_fields if isinstance(numeric_fields, dict) else {}

    skills_payload = set_fields.get("skills")
    if not isinstance(skills_payload, dict):
        skills_payload = set_fields.get("skills_tokens")
    skills_payload = skills_payload if isinstance(skills_payload, dict) else {}
    skill_tokens_added = _safe_ui_tokens(skills_payload.get("added"), lowercase=True)
    skill_tokens_removed = _safe_ui_tokens(skills_payload.get("removed"), lowercase=True)

    seniority_from, seniority_to = _extract_string_transition(
        string_fields,
        field_names=("seniority", "seniority_tokens"),
    )
    location_from, location_to = _extract_string_transition(string_fields, field_names=("location",))
    compensation_before, compensation_after = _extract_compensation_window(numeric_fields)

    seniority_shift = (
        "seniority" in changed_fields or "seniority_tokens" in changed_fields or bool(seniority_from or seniority_to)
    )
    location_shift = "location" in changed_fields or bool(location_from or location_to)
    compensation_shift = (
        "compensation" in changed_fields or compensation_before is not None or compensation_after is not None
    )
    skill_token_delta = len(skill_tokens_added) + len(skill_tokens_removed)
    significance_score = (
        skill_token_delta
        + (3 if seniority_shift else 0)
        + (2 if location_shift else 0)
        + (2 if compensation_shift else 0)
    )
    notable = skill_token_delta >= _MIN_SKILL_TOKEN_DELTA or seniority_shift or location_shift or compensation_shift

    return {
        "from_observation_id": _safe_ui_text(change.get("from_observation_id"), max_len=128),
        "to_observation_id": to_observation_id,
        "change_hash": _safe_ui_text(change.get("change_hash"), max_len=128),
        "observed_at_utc": _utc_iso(observed_dt),
        "changed_fields": changed_fields,
        "skill_tokens_added": skill_tokens_added,
        "skill_tokens_removed": skill_tokens_removed,
        "seniority_from": seniority_from,
        "seniority_to": seniority_to,
        "location_from": location_from,
        "location_to": location_to,
        "compensation_before": compensation_before,
        "compensation_after": compensation_after,
        "seniority_shift": seniority_shift,
        "location_shift": location_shift,
        "compensation_shift": compensation_shift,
        "significance_score": significance_score,
        "notable": notable,
        "_observed_dt": observed_dt,
        "_job_hash": _safe_ui_text(job.get("job_hash"), max_len=128),
        "_provider_id": _safe_ui_text(job.get("provider_id"), max_len=64),
        "_canonical_url": _safe_ui_text(job.get("canonical_url"), max_len=512),
    }


def _project_timeline_changes(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = job.get("changes")
    if not isinstance(raw, list):
        return []
    lookup = _timeline_observation_lookup(job)
    projected: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        row = _project_timeline_change(job, item, observation_lookup=lookup)
        if row is None:
            continue
        projected.append(row)
    projected.sort(
        key=lambda row: (
            str(row.get("observed_at_utc") or ""),
            str(row.get("to_observation_id") or ""),
            str(row.get("change_hash") or ""),
        )
    )
    return projected[:_MAX_TIMELINE_CHANGES]


def _project_job_timeline(job: Dict[str, Any]) -> Dict[str, Any]:
    projected_changes = _project_timeline_changes(job)
    changes = [
        {
            key: row[key]
            for key in (
                "from_observation_id",
                "to_observation_id",
                "change_hash",
                "observed_at_utc",
                "changed_fields",
                "skill_tokens_added",
                "skill_tokens_removed",
                "seniority_from",
                "seniority_to",
                "location_from",
                "location_to",
                "compensation_before",
                "compensation_after",
                "seniority_shift",
                "location_shift",
                "compensation_shift",
                "significance_score",
                "notable",
            )
        }
        for row in projected_changes
    ]
    return {
        "job_hash": _safe_ui_text(job.get("job_hash"), max_len=128),
        "provider_id": _safe_ui_text(job.get("provider_id"), max_len=64),
        "canonical_url": _safe_ui_text(job.get("canonical_url"), max_len=512),
        "observations": _project_timeline_observations(job),
        "changes": changes,
    }


def _load_job_timeline_jobs(run_id: str, candidate_id: str, index: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    timeline_payload = _read_artifact_json_value(run_id, candidate_id, index, "job_timeline_v1.json", required=False)
    if timeline_payload is None:
        return None
    if not isinstance(timeline_payload, dict):
        raise HTTPException(status_code=500, detail="job_timeline_v1.json invalid shape")
    jobs = timeline_payload.get("jobs")
    if not isinstance(jobs, list):
        raise HTTPException(status_code=500, detail="job_timeline_v1.json invalid shape")
    return [job for job in jobs if isinstance(job, dict)]


def _empty_recent_changes_payload(reference_dt: datetime) -> Dict[str, Any]:
    window_start = reference_dt - timedelta(days=_RECENT_CHANGES_WINDOW_DAYS)
    return {
        "window_days": _RECENT_CHANGES_WINDOW_DAYS,
        "window_start_utc": _utc_iso(window_start),
        "window_end_utc": _utc_iso(reference_dt),
        "change_event_count": 0,
        "notable_changes": [],
    }


def _project_recent_changes(
    timeline_jobs: List[Dict[str, Any]],
    *,
    top_jobs: List[Dict[str, Any]],
    reference_dt: datetime,
    top_n: int,
) -> Dict[str, Any]:
    out = _empty_recent_changes_payload(reference_dt)
    window_start = reference_dt - timedelta(days=_RECENT_CHANGES_WINDOW_DAYS)
    top_jobs_by_hash: Dict[str, Dict[str, Any]] = {}
    for job in top_jobs:
        if not isinstance(job, dict):
            continue
        job_hash = _safe_ui_text(job.get("job_hash"), max_len=128)
        if job_hash:
            top_jobs_by_hash[job_hash] = job

    events: List[Dict[str, Any]] = []
    for job in timeline_jobs:
        for row in _project_timeline_changes(job):
            observed_dt = row.get("_observed_dt")
            if not isinstance(observed_dt, datetime):
                continue
            if not (window_start < observed_dt <= reference_dt):
                continue
            if not bool(row.get("notable")):
                continue
            job_hash = str(row.get("_job_hash") or "")
            top_lookup = top_jobs_by_hash.get(job_hash, {})
            events.append(
                {
                    "job_hash": job_hash,
                    "change_hash": row.get("change_hash"),
                    "observed_at_utc": row.get("observed_at_utc"),
                    "provider_id": row.get("_provider_id") or top_lookup.get("provider"),
                    "title": top_lookup.get("title"),
                    "company": top_lookup.get("company"),
                    "canonical_url": row.get("_canonical_url"),
                    "changed_fields": row.get("changed_fields"),
                    "skill_tokens_added": row.get("skill_tokens_added"),
                    "skill_tokens_removed": row.get("skill_tokens_removed"),
                    "seniority_shift": bool(row.get("seniority_shift")),
                    "location_shift": bool(row.get("location_shift")),
                    "compensation_shift": bool(row.get("compensation_shift")),
                    "significance_score": int(row.get("significance_score") or 0),
                    "_observed_dt": observed_dt,
                }
            )

    events.sort(
        key=lambda row: (
            -int(row.get("significance_score") or 0),
            -int(row.get("_observed_dt").timestamp()) if isinstance(row.get("_observed_dt"), datetime) else 0,
            str(row.get("job_hash") or ""),
            str(row.get("change_hash") or ""),
        )
    )
    out["change_event_count"] = len(events)
    out["notable_changes"] = [
        {
            key: row[key]
            for key in (
                "job_hash",
                "change_hash",
                "observed_at_utc",
                "provider_id",
                "title",
                "company",
                "canonical_url",
                "changed_fields",
                "skill_tokens_added",
                "skill_tokens_removed",
                "seniority_shift",
                "location_shift",
                "compensation_shift",
                "significance_score",
            )
        }
        for row in events[: max(1, min(top_n, 20))]
    ]
    return out


def _read_s3_json(bucket: str, key: str) -> Tuple[Optional[Dict[str, Any]], str]:
    s3 = boto3.client("s3")
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404"}:
            return None, "not_found"
        if code in {"AccessDenied", "403"}:
            return None, "access_denied"
        return None, f"error:{code or exc.__class__.__name__}"
    body = resp.get("Body")
    if body is None:
        return None, "empty_body"
    max_bytes = _max_json_bytes()
    content_length = resp.get("ContentLength")
    if isinstance(content_length, int) and content_length > max_bytes:
        logger.warning(
            "S3 JSON payload too large: s3://%s/%s bytes=%d limit=%d", bucket, key, content_length, max_bytes
        )
        return None, "too_large"
    try:
        raw = body.read(max_bytes + 1)
        if len(raw) > max_bytes:
            logger.warning("S3 JSON payload exceeded read limit: s3://%s/%s limit=%d", bucket, key, max_bytes)
            return None, "too_large"
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return None, "invalid_json"
    if not isinstance(payload, dict):
        return None, "invalid_shape"
    return payload, "ok"


def _local_proof_path(run_id: str, candidate_id: str) -> Path:
    safe_candidate = _sanitize_candidate_id(candidate_id)
    namespaced = candidate_state_paths(safe_candidate).proofs_dir / f"{run_id}.json"
    if namespaced.exists():
        return namespaced
    if safe_candidate == DEFAULT_CANDIDATE_ID:
        return STATE_DIR / "proofs" / f"{run_id}.json"
    return namespaced


def _s3_proof_key(prefix: str, run_id: str, candidate_id: str) -> str:
    safe_candidate = _sanitize_candidate_id(candidate_id)
    return f"{prefix}/state/candidates/{safe_candidate}/proofs/{run_id}.json".strip("/")


def _s3_legacy_proof_key(prefix: str, run_id: str) -> str:
    return f"{prefix}/state/proofs/{run_id}.json".strip("/")


def _s3_latest_prefix(prefix: str, provider: str, profile: str, candidate_id: str) -> str:
    safe_candidate = _sanitize_candidate_id(candidate_id)
    if safe_candidate == DEFAULT_CANDIDATE_ID:
        return f"{prefix}/latest/{provider}/{profile}/".strip("/")
    return f"{prefix}/candidates/{safe_candidate}/latest/{provider}/{profile}/".strip("/")


def _s3_legacy_latest_prefix(prefix: str, provider: str, profile: str) -> str:
    return f"{prefix}/latest/{provider}/{profile}/".strip("/")


def _s3_list_keys(bucket: str, prefix: str) -> List[str]:
    s3 = boto3.client("s3")
    keys: List[str] = []
    token = None
    while True:
        kwargs: Dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents") or []:
            key = obj.get("Key")
            if key:
                keys.append(key)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def _version_payload() -> Dict[str, Any]:
    """Build /version response. Stable shape for UI readiness."""
    git_sha = (os.environ.get("JOBINTEL_GIT_SHA") or os.environ.get("GIT_SHA") or "unknown").strip() or "unknown"
    build_ts = (os.environ.get("JOBINTEL_BUILD_TIMESTAMP") or os.environ.get("BUILD_TIMESTAMP") or "").strip()
    schema_versions: Dict[str, int] = {
        "run_summary": 1,
        "run_health": 1,
    }
    out: Dict[str, Any] = {
        "service": "SignalCraft",
        "git_sha": git_sha,
        "schema_versions": schema_versions,
    }
    if build_ts:
        out["build_timestamp"] = build_ts
    return out


@app.get("/version")
def version() -> Dict[str, Any]:
    """Return service identity and schema versions for UI readiness."""
    return _version_payload()


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ui")
def ui_v0() -> Response:
    if not _UI_V0_HTML.exists():
        raise HTTPException(status_code=500, detail="UI bundle not found")
    return FileResponse(_UI_V0_HTML, media_type="text/html")


@app.get("/runs")
def runs(candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Dict[str, Any]]:
    return _list_runs(candidate_id)


@app.get("/runs/{run_id}")
def run_detail(run_id: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
    _sanitize_run_id(run_id)
    index = _load_index(run_id, candidate_id)
    run_dir = _run_dir(run_id, candidate_id)
    run_report = (
        _load_optional_json_object(run_dir / "run_report.json", context="run report", schema=_RunReportSchema) or {}
    )
    costs = _load_optional_json_object(run_dir / "costs.json", context="run costs")
    prompt_version = _load_first_ai_prompt_version(run_id, candidate_id, index)
    enriched: Dict[str, Any] = dict(index)
    enriched["semantic_enabled"] = bool(run_report.get("semantic_enabled", False))
    enriched["semantic_mode"] = run_report.get("semantic_mode")
    enriched["ai_prompt_version"] = prompt_version
    enriched["cost_summary"] = costs
    _ensure_ui_safe(enriched, context="run_detail")
    return enriched


def _enforce_artifact_model(
    artifact_key: str,
    run_id: str,
    path: Path,
    max_bytes: int,
) -> Optional[bytes]:
    """
    Enforce artifact model v2 at serving boundary.
    Returns bytes to serve. Raises HTTPException on fail-closed.
    """
    category = get_artifact_category(artifact_key)
    if category == ArtifactCategory.UNCATEGORIZED:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "artifact_uncategorized",
                "artifact_key": artifact_key,
                "run_id": run_id,
                "message": "Artifact not in catalog; fail-closed.",
            },
        )
    size = path.stat().st_size
    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={"error": "artifact_too_large", "message": "Artifact payload too large", "max_bytes": max_bytes},
        )
    if path.suffix.lower() != ".json":
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Artifact invalid shape")
    try:
        validate_artifact_payload(payload, artifact_key, run_id, category)
    except ValueError as exc:
        try:
            detail = json.loads(str(exc))
        except json.JSONDecodeError:
            detail = {"error": "validation_failed", "message": str(exc)}
        raise HTTPException(status_code=500, detail=detail) from exc
    # Redact forbidden JD fields from replay_safe before serving (no raw JD leakage)
    if category == ArtifactCategory.REPLAY_SAFE:
        payload = redact_forbidden_fields(payload)
        if not isinstance(payload, dict):
            payload = {}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@app.get("/runs/{run_id}/artifact/{name}")
def run_artifact(run_id: str, name: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Response:
    _sanitize_run_id(run_id)
    safe_run_id = run_id.strip()
    index = _load_index(run_id, candidate_id)
    path = _resolve_artifact_path(run_id, candidate_id, index, name)
    max_bytes = _max_json_bytes()
    body = _enforce_artifact_model(name, safe_run_id, path, max_bytes)
    if body is not None:
        return Response(body, media_type=_content_type(path))
    return FileResponse(path, media_type=_content_type(path))


def _provider_profile_pairs_for_semantic(index: Dict[str, Any], run_dir: Path, profile: str) -> List[Tuple[str, str]]:
    """Index-backed: derive (provider, profile) pairs from index.providers, run_report, or index.artifacts."""
    pairs: List[Tuple[str, str]] = []
    providers = index.get("providers") if isinstance(index.get("providers"), dict) else {}
    for prov, prov_data in providers.items():
        if isinstance(prov_data, dict):
            profiles_dict = prov_data.get("profiles") or {}
            if isinstance(profiles_dict, dict) and profile in profiles_dict:
                pairs.append((prov, profile))
    if pairs:
        return sorted(pairs)
    run_report = (
        _load_optional_json_object(run_dir / "run_report.json", context="run report", schema=_RunReportSchema) or {}
    )
    outputs = run_report.get("outputs_by_provider") or {}
    for prov, prov_data in outputs.items():
        if isinstance(prov_data, dict) and profile in prov_data:
            pairs.append((prov, profile))
    if pairs:
        return sorted(pairs)
    artifacts = index.get("artifacts") if isinstance(index.get("artifacts"), dict) else {}
    prefix, suffix = "semantic/scores_", f"_{profile}.json"
    for key in artifacts:
        if key.startswith(prefix) and key.endswith(suffix) and len(key) > len(prefix) + len(suffix):
            prov = key[len(prefix) : -len(suffix)]
            if prov and "/" not in prov and ".." not in prov:
                pairs.append((prov, profile))
    return sorted(pairs)


@app.get("/runs/{run_id}/semantic_summary/{profile}")
def run_semantic_summary(run_id: str, profile: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
    _sanitize_run_id(run_id)
    index = _load_index(run_id, candidate_id)
    run_dir = _run_dir(run_id, candidate_id)
    summary_rel = "semantic/semantic_summary.json"
    safe_candidate = _sanitize_candidate_id(candidate_id)
    try:
        summary_path = RUN_REPOSITORY.resolve_run_artifact_path(run_id, summary_rel, candidate_id=safe_candidate)
    except ValueError:
        raise HTTPException(status_code=404, detail="Semantic summary not found") from None
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Semantic summary not found")
    try:
        summary = _read_local_json_object(summary_path)
    except _DashboardJsonError as exc:
        logger.warning("Semantic summary read failed at %s (%s)", summary_path, exc.code)
        if exc.code == "too_large":
            raise HTTPException(status_code=413, detail="Semantic summary payload too large") from exc
        if exc.code == "invalid_json":
            raise HTTPException(status_code=500, detail="Semantic summary invalid JSON") from exc
        raise HTTPException(status_code=500, detail="Semantic summary has invalid shape") from exc

    entries: List[Dict[str, Any]] = []
    for prov, prof in _provider_profile_pairs_for_semantic(index, run_dir, profile):
        scores_rel = f"semantic/scores_{prov}_{prof}.json"
        try:
            path = RUN_REPOSITORY.resolve_run_artifact_path(run_id, scores_rel, candidate_id=safe_candidate)
        except ValueError:
            continue
        if not path.exists() or not path.is_file():
            continue
        payload = _load_optional_json_object(path, context="semantic scores payload")
        if not payload:
            continue
        payload_entries = payload.get("entries")
        if not isinstance(payload_entries, list):
            continue
        for item in payload_entries:
            if isinstance(item, dict):
                entries.append(item)

    entries.sort(key=lambda item: (str(item.get("provider") or ""), str(item.get("job_id") or "")))
    response: Dict[str, Any] = {"run_id": run_id, "profile": profile, "summary": summary, "entries": entries}
    _ensure_ui_safe(response, context="run_semantic_summary")
    return response


@app.get("/v1/ui/latest")
def ui_latest(candidate_id: str = DEFAULT_CANDIDATE_ID, top_n: int = 10) -> Dict[str, Any]:
    """
    UI v0 aggregate payload for read-only product surface.
    Reads only UI-safe fields with bounded artifact reads.
    """
    if top_n < 1 or top_n > 50:
        raise HTTPException(status_code=400, detail="Invalid top_n")
    safe_candidate = _sanitize_candidate_id(candidate_id)
    latest_payload = latest(candidate_id=safe_candidate)
    pointer = latest_payload.get("payload")
    if not isinstance(pointer, dict):
        raise HTTPException(status_code=500, detail="Latest payload has invalid shape")
    run_id = pointer.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise HTTPException(status_code=404, detail="Latest run_id not found")

    run_view = run_detail(run_id, candidate_id=safe_candidate)
    index = _load_index(run_id, safe_candidate)
    top_jobs_key = _find_first_artifact_name(index, "*ranked_jobs*.json")

    explanation = _read_artifact_json_value(run_id, safe_candidate, index, "explanation_v1.json", required=False)
    provider_availability = _read_artifact_json_value(
        run_id,
        safe_candidate,
        index,
        "provider_availability_v1.json",
        required=False,
    )
    run_health = _read_artifact_json_value(run_id, safe_candidate, index, "run_health.v1.json", required=False)
    top_jobs: List[Dict[str, Any]] = []
    if top_jobs_key:
        ranked_payload = _read_artifact_json_value(run_id, safe_candidate, index, top_jobs_key, required=True)
        if ranked_payload is not None:
            top_jobs = _project_top_jobs(ranked_payload, top_n=top_n)
    reference_dt = _safe_parse_utc(run_view.get("timestamp") or run_id) or datetime(1970, 1, 1, tzinfo=timezone.utc)
    timeline_jobs = _load_job_timeline_jobs(run_id, safe_candidate, index)
    recent_changes = _empty_recent_changes_payload(reference_dt)
    if timeline_jobs:
        recent_changes = _project_recent_changes(
            timeline_jobs,
            top_jobs=top_jobs,
            reference_dt=reference_dt,
            top_n=top_n,
        )

    response: Dict[str, Any] = {
        "candidate_id": safe_candidate,
        "run_id": run_id,
        "latest_source": latest_payload.get("source"),
        "run": {
            "run_id": run_view.get("run_id"),
            "timestamp": run_view.get("timestamp"),
            "status": run_view.get("status"),
            "semantic_enabled": bool(run_view.get("semantic_enabled", False)),
            "semantic_mode": run_view.get("semantic_mode"),
            "ai_prompt_version": run_view.get("ai_prompt_version"),
            "cost_summary": run_view.get("cost_summary"),
        },
        "top_jobs": top_jobs,
        "top_jobs_artifact": top_jobs_key,
        "explanation": explanation if isinstance(explanation, dict) else None,
        "provider_availability": provider_availability if isinstance(provider_availability, dict) else None,
        "run_health": run_health if isinstance(run_health, dict) else None,
        "recent_changes": recent_changes,
    }
    _ensure_ui_safe(response, context="ui_latest")
    return response


@app.get("/v1/jobs/{job_hash}/timeline")
def job_timeline(job_hash: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
    safe_job_hash = _sanitize_job_hash(job_hash)
    safe_candidate = _sanitize_candidate_id(candidate_id)
    latest_payload = latest(candidate_id=safe_candidate)
    pointer = latest_payload.get("payload")
    if not isinstance(pointer, dict):
        raise HTTPException(status_code=500, detail="Latest payload has invalid shape")
    run_id = pointer.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise HTTPException(status_code=404, detail="Latest run_id not found")

    index = _load_index(run_id, safe_candidate)
    timeline_jobs = _load_job_timeline_jobs(run_id, safe_candidate, index)
    if timeline_jobs is None:
        raise HTTPException(status_code=404, detail="job_timeline_v1.json not found")

    selected: Optional[Dict[str, Any]] = None
    for job in timeline_jobs:
        if _safe_ui_text(job.get("job_hash"), max_len=128) == safe_job_hash:
            selected = job
            break
    if selected is None:
        raise HTTPException(status_code=404, detail="job_hash not found")

    response = {
        "candidate_id": safe_candidate,
        "latest_source": latest_payload.get("source"),
        "run_id": run_id,
        "job_hash": safe_job_hash,
        "timeline": _project_job_timeline(selected),
    }
    _ensure_ui_safe(response, context="job_timeline")
    return response


@app.get("/v1/profile")
def profile_read(candidate_id: Optional[str] = None) -> Dict[str, Any]:
    safe_candidate = _resolve_candidate_or_active(candidate_id)
    try:
        payload = candidate_registry.profile_contract(safe_candidate)
    except candidate_registry.CandidateValidationError as exc:
        message = str(exc)
        if "missing" in message:
            raise HTTPException(status_code=404, detail="Candidate profile not found") from exc
        raise HTTPException(status_code=500, detail="Candidate profile is invalid") from exc
    _ensure_ui_safe(payload, context="profile_read")
    return payload


@app.put("/v1/profile")
def profile_write(update: _ProfileUpdateRequest, candidate_id: Optional[str] = None) -> Dict[str, Any]:
    safe_candidate = _resolve_candidate_or_active(candidate_id)
    try:
        candidate_registry.update_candidate_profile(
            safe_candidate,
            display_name=update.display_name,
            seniority=update.profile_fields.seniority,
            role_archetype=update.profile_fields.role_archetype,
            location=update.profile_fields.location,
            skills=update.profile_fields.skills,
        )
        payload = candidate_registry.profile_contract(safe_candidate)
    except candidate_registry.CandidateValidationError as exc:
        message = str(exc)
        if "at least one profile field is required" in message:
            raise HTTPException(status_code=400, detail=message) from exc
        if "missing" in message:
            raise HTTPException(status_code=404, detail="Candidate profile not found") from exc
        raise HTTPException(status_code=500, detail="Candidate profile update failed") from exc
    _ensure_ui_safe(payload, context="profile_write")
    return payload


@app.get("/v1/latest")
def latest(candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
    safe_candidate = _sanitize_candidate_id(candidate_id)
    if _s3_enabled():
        bucket = _s3_bucket()
        prefix = _s3_prefix()
        payload, status, key = aws_runs.read_last_success_state(bucket, prefix, candidate_id=safe_candidate)
        if status != "ok" or not payload:
            raise HTTPException(status_code=404, detail=f"s3 last_success not found ({status})")
        _ensure_ui_safe(payload, context="latest")
        return {
            "source": "s3",
            "candidate_id": safe_candidate,
            "bucket": bucket,
            "prefix": prefix,
            "key": key,
            "payload": payload,
        }
    pointer_path = _state_last_success_path(safe_candidate)
    payload = _read_local_json(pointer_path)
    _ensure_ui_safe(payload, context="latest")
    return {"source": "local", "candidate_id": safe_candidate, "path": str(pointer_path), "payload": payload}


@app.get("/v1/runs/{run_id}")
def run_receipt(run_id: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
    _sanitize_run_id(run_id)
    safe_candidate = _sanitize_candidate_id(candidate_id)
    if _s3_enabled():
        bucket = _s3_bucket()
        prefix = _s3_prefix()
        proof_key = _s3_proof_key(prefix, run_id, safe_candidate)
        payload, status = _read_s3_json(bucket, proof_key)
        if status != "ok" and safe_candidate == DEFAULT_CANDIDATE_ID:
            legacy_key = _s3_legacy_proof_key(prefix, run_id)
            payload, status = _read_s3_json(bucket, legacy_key)
            proof_key = legacy_key
        if status == "ok" and payload:
            _ensure_ui_safe(payload, context="run_receipt")
            return {"source": "s3", "bucket": bucket, "prefix": prefix, "key": proof_key, "payload": payload}
    local_path = _local_proof_path(run_id, safe_candidate)
    payload = _read_local_json(local_path)
    _ensure_ui_safe(payload, context="run_receipt")
    return {"source": "local", "path": str(local_path), "payload": payload}


@app.get("/v1/runs/{run_id}/artifacts")
def run_artifact_index(run_id: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
    """
    Stable artifact index for a run. Bounded: no raw artifact bodies.
    Returns { run_id, candidate_id, artifacts: [{key, schema_version, path, content_type, size_bytes?}] }
    """
    _sanitize_run_id(run_id)
    safe_candidate = _sanitize_candidate_id(candidate_id)
    index = _load_index(run_id, candidate_id)
    artifacts_map = index.get("artifacts")
    if not isinstance(artifacts_map, dict):
        artifacts_map = {}
    entries: List[Dict[str, Any]] = []
    for key, rel in sorted(artifacts_map.items()):
        if not isinstance(rel, str) or not rel.strip():
            continue
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            continue
        try:
            full_path = RUN_REPOSITORY.resolve_run_artifact_path(
                run_id, rel_path.as_posix(), candidate_id=safe_candidate
            )
        except ValueError:
            continue
        content_type = _content_type(full_path)
        schema_version = _schema_version_for_artifact_key(key)
        entry: Dict[str, Any] = {
            "key": key,
            "path": rel,
            "content_type": content_type,
        }
        if schema_version is not None:
            entry["schema_version"] = schema_version
        if full_path.exists() and full_path.is_file():
            try:
                size = full_path.stat().st_size
                entry["size_bytes"] = size
            except OSError:
                pass
        entries.append(entry)
    return {
        "run_id": run_id,
        "candidate_id": safe_candidate,
        "artifacts": entries,
    }


@app.get("/v1/artifacts/latest/{provider}/{profile}")
def latest_artifacts(provider: str, profile: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
    safe_candidate = _sanitize_candidate_id(candidate_id)
    if _s3_enabled():
        bucket = _s3_bucket()
        prefix = _s3_prefix()
        latest_prefix = _s3_latest_prefix(prefix, provider, profile, safe_candidate)
        keys = _s3_list_keys(bucket, latest_prefix)
        if not keys and safe_candidate == DEFAULT_CANDIDATE_ID:
            latest_prefix = _s3_legacy_latest_prefix(prefix, provider, profile)
            keys = _s3_list_keys(bucket, latest_prefix)
        return {"source": "s3", "bucket": bucket, "prefix": latest_prefix, "keys": keys}

    pointer = _read_local_json(_state_last_success_path(safe_candidate))
    run_id = pointer.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Local last_success missing run_id")
    run_dir = _run_dir(run_id, safe_candidate)
    report_path = run_dir / "run_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Local run_report not found")
    report = _read_local_json(report_path)
    outputs = report.get("outputs_by_provider", {}).get(provider, {}).get(profile, {})
    if not isinstance(outputs, dict) or not outputs:
        raise HTTPException(status_code=404, detail="No artifacts for provider/profile")
    files = [item.get("path") for item in outputs.values() if isinstance(item, dict) and item.get("path")]
    return {
        "source": "local",
        "run_id": run_id,
        "paths": files,
    }
