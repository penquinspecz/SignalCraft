"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

import boto3
from botocore.exceptions import ClientError

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import Response
    from pydantic import BaseModel, ConfigDict, Field, ValidationError
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in environments without dashboard extras
    raise RuntimeError("Dashboard dependencies are not installed. Install with: pip install -e '.[dashboard]'") from exc

from ji_engine.artifacts.catalog import (
    ArtifactCategory,
    get_artifact_category,
    redact_forbidden_fields,
    validate_artifact_payload,
)
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
_DEFAULT_MAX_JSON_BYTES = 2 * 1024 * 1024


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


def _read_local_json_object(path: Path, *, schema: Optional[Type[BaseModel]] = None) -> Dict[str, Any]:
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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _DashboardJsonError("invalid_json") from exc
    except OSError as exc:
        raise _DashboardJsonError("io_error") from exc
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


def _sanitize_run_id(run_id: str) -> str:
    if not isinstance(run_id, str):
        raise HTTPException(status_code=400, detail="Invalid run_id")
    raw = run_id.strip()
    if not _RUN_ID_RE.fullmatch(raw):
        raise HTTPException(status_code=400, detail="Invalid run_id")
    return raw.replace(":", "").replace("-", "").replace(".", "")


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
    if key == "run_summary.v1.json":
        return 1
    if key == "run_health.v1.json":
        return 1
    if key == "provider_availability_v1.json":
        return 1
    if key == "run_report.json":
        return 1
    return None


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
    return redact_forbidden_fields(enriched)


def _enforce_artifact_model(
    artifact_key: str,
    run_id: str,
    path: Path,
    max_bytes: int,
) -> bytes:
    """
    Enforce artifact model v2 at serving boundary.
    Returns bytes to serve. Raises HTTPException on fail-closed.
    """
    if path.suffix.lower() != ".json":
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
        return path.read_bytes()
    size = path.stat().st_size
    if size > max_bytes:
        raise HTTPException(status_code=413, detail="Artifact payload too large")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Artifact invalid shape")
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
    return Response(body, media_type=_content_type(path))


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
    return redact_forbidden_fields(response)


@app.get("/v1/latest")
def latest(candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
    safe_candidate = _sanitize_candidate_id(candidate_id)
    if _s3_enabled():
        bucket = _s3_bucket()
        prefix = _s3_prefix()
        payload, status, key = aws_runs.read_last_success_state(bucket, prefix, candidate_id=safe_candidate)
        if status != "ok" or not payload:
            raise HTTPException(status_code=404, detail=f"s3 last_success not found ({status})")
        return {
            "source": "s3",
            "bucket": bucket,
            "prefix": prefix,
            "key": key,
            "payload": redact_forbidden_fields(payload),
        }
    pointer_path = _state_last_success_path(safe_candidate)
    payload = _read_local_json(pointer_path)
    return {"source": "local", "path": str(pointer_path), "payload": redact_forbidden_fields(payload)}


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
            return {
                "source": "s3",
                "bucket": bucket,
                "prefix": prefix,
                "key": proof_key,
                "payload": redact_forbidden_fields(payload),
            }
    local_path = _local_proof_path(run_id, safe_candidate)
    payload = _read_local_json(local_path)
    return {"source": "local", "path": str(local_path), "payload": redact_forbidden_fields(payload)}


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
