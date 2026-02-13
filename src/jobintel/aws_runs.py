"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from ji_engine.config import DEFAULT_CANDIDATE_ID, sanitize_candidate_id
from ji_engine.utils.time import utc_now_z


@dataclass
class BaselineInfo:
    run_id: Optional[str]
    source: str
    path: Optional[str]
    ranked_path: Optional[Path]


def _parse_run_id(run_id: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(run_id.replace("Z", "+00:00"))
    except Exception:
        return None


def _get_client(client=None):
    return client or boto3.client("s3")


def _runs_prefix(prefix: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> str:
    clean = prefix.strip("/")
    safe_candidate = sanitize_candidate_id(candidate_id)
    if safe_candidate == DEFAULT_CANDIDATE_ID:
        return f"{clean}/runs/" if clean else "runs/"
    return f"{clean}/candidates/{safe_candidate}/runs/" if clean else f"candidates/{safe_candidate}/runs/"


def parse_run_id_from_key(key: str, prefix: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Optional[str]:
    runs_prefix = _runs_prefix(prefix, candidate_id)
    if runs_prefix not in key:
        return None
    rest = key.split(runs_prefix, 1)[1]
    run_id = rest.split("/", 1)[0]
    return run_id or None


def get_most_recent_run_id_before(
    bucket: str,
    prefix: str,
    current_run_id: str,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    client=None,
) -> Optional[str]:
    s3 = _get_client(client)
    runs_prefix = _runs_prefix(prefix, candidate_id)
    run_ids: set[str] = set()
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": runs_prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents") or []:
            key = obj.get("Key") or ""
            run_id = parse_run_id_from_key(key, prefix, candidate_id)
            if run_id:
                run_ids.add(run_id)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")

    current_dt = _parse_run_id(current_run_id)
    candidates = []
    for run_id in run_ids:
        if run_id == current_run_id:
            continue
        run_dt = _parse_run_id(run_id)
        if current_dt and run_dt and run_dt < current_dt:
            candidates.append((run_dt, run_id))
        elif current_dt is None:
            candidates.append((run_id, run_id))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def _run_report_key(prefix: str, run_id: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> str:
    clean = prefix.strip("/")
    safe_candidate = sanitize_candidate_id(candidate_id)
    if safe_candidate == DEFAULT_CANDIDATE_ID:
        return f"{clean}/runs/{run_id}/run_report.json".strip("/")
    return f"{clean}/candidates/{safe_candidate}/runs/{run_id}/run_report.json".strip("/")


def _read_json_object(bucket: str, key: str, *, client=None) -> tuple[Optional[dict], str]:
    s3 = _get_client(client)
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404"}:
            return None, "not_found"
        if code in {"AccessDenied", "403"}:
            return None, "access_denied"
        return None, f"error:{code or exc.__class__.__name__}"
    except Exception as exc:
        return None, f"error:{exc.__class__.__name__}"
    body = resp.get("Body")
    if body is None:
        return None, "empty_body"
    try:
        data = json.loads(body.read().decode("utf-8"))
    except Exception:
        return None, "invalid_json"
    if not isinstance(data, dict):
        return None, "invalid_shape"
    return data, "ok"


def get_most_recent_successful_run_id_before(
    bucket: str,
    prefix: str,
    current_run_id: str,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    client=None,
) -> Optional[str]:
    s3 = _get_client(client)
    runs_prefix = _runs_prefix(prefix, candidate_id)
    run_ids: set[str] = set()
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": runs_prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents") or []:
            key = obj.get("Key") or ""
            run_id = parse_run_id_from_key(key, prefix, candidate_id)
            if run_id:
                run_ids.add(run_id)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")

    current_dt = _parse_run_id(current_run_id)
    candidates = []
    for run_id in run_ids:
        if run_id == current_run_id:
            continue
        run_dt = _parse_run_id(run_id)
        if current_dt and run_dt and run_dt < current_dt:
            candidates.append((run_dt, run_id))
        elif current_dt is None:
            candidates.append((run_id, run_id))
    if not candidates:
        return None
    candidates.sort()
    for _, run_id in reversed(candidates):
        report_key = _run_report_key(prefix, run_id, candidate_id)
        payload, status = _read_json_object(bucket, report_key, client=client)
        if status != "ok" or not payload:
            continue
        if payload.get("success") is True:
            return run_id
    return None


def _state_key(prefix: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> str:
    safe_candidate = sanitize_candidate_id(candidate_id)
    return f"{prefix.strip('/')}/state/candidates/{safe_candidate}/last_success.json".strip("/")


def _legacy_state_key(prefix: str) -> str:
    return f"{prefix.strip('/')}/state/last_success.json".strip("/")


def _provider_state_key(
    prefix: str,
    provider: str,
    profile: str,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
) -> str:
    safe_candidate = sanitize_candidate_id(candidate_id)
    return f"{prefix.strip('/')}/state/candidates/{safe_candidate}/{provider}/{profile}/last_success.json".strip("/")


def _legacy_provider_state_key(prefix: str, provider: str, profile: str) -> str:
    return f"{prefix.strip('/')}/state/{provider}/{profile}/last_success.json".strip("/")


def read_last_success_state(
    bucket: str,
    prefix: str,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    client=None,
) -> tuple[Optional[dict], str, str]:
    safe_candidate = sanitize_candidate_id(candidate_id)
    key = _state_key(prefix, safe_candidate)
    payload, status = _read_json_object(bucket, key, client=client)
    if status == "ok":
        return payload, status, key
    if safe_candidate == DEFAULT_CANDIDATE_ID:
        legacy_key = _legacy_state_key(prefix)
        payload, legacy_status = _read_json_object(bucket, legacy_key, client=client)
        if legacy_status == "ok":
            return payload, legacy_status, legacy_key
    return payload, status, key


def read_provider_last_success_state(
    bucket: str,
    prefix: str,
    provider: str,
    profile: str,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    client=None,
) -> tuple[Optional[dict], str, str]:
    safe_candidate = sanitize_candidate_id(candidate_id)
    key = _provider_state_key(prefix, provider, profile, safe_candidate)
    payload, status = _read_json_object(bucket, key, client=client)
    if status == "ok":
        return payload, status, key
    if safe_candidate == DEFAULT_CANDIDATE_ID:
        legacy_key = _legacy_provider_state_key(prefix, provider, profile)
        payload, legacy_status = _read_json_object(bucket, legacy_key, client=client)
        if legacy_status == "ok":
            return payload, legacy_status, legacy_key
    return payload, status, key


def get_last_success_state(
    bucket: str,
    prefix: str,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    client=None,
) -> Optional[dict]:
    payload, status, _ = read_last_success_state(bucket, prefix, candidate_id=candidate_id, client=client)
    if status != "ok":
        return None
    return payload


def get_provider_last_success_state(
    bucket: str,
    prefix: str,
    provider: str,
    profile: str,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    client=None,
) -> Optional[dict]:
    payload, status, _ = read_provider_last_success_state(
        bucket,
        prefix,
        provider,
        profile,
        candidate_id=candidate_id,
        client=client,
    )
    if status != "ok":
        return None
    return payload


def write_last_success_state(
    bucket: str,
    prefix: str,
    payload: dict,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    write_legacy_for_local: bool = True,
    client=None,
) -> None:
    s3 = _get_client(client)
    safe_candidate = sanitize_candidate_id(candidate_id)
    key = _state_key(prefix, safe_candidate)
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=encoded)
    # Compatibility: local candidate keeps the legacy global pointer for existing consumers.
    if safe_candidate == DEFAULT_CANDIDATE_ID and write_legacy_for_local:
        s3.put_object(Bucket=bucket, Key=_legacy_state_key(prefix), Body=encoded)


def write_provider_last_success_state(
    bucket: str,
    prefix: str,
    provider: str,
    profile: str,
    payload: dict,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    write_legacy_for_local: bool = True,
    client=None,
) -> None:
    s3 = _get_client(client)
    safe_candidate = sanitize_candidate_id(candidate_id)
    key = _provider_state_key(prefix, provider, profile, safe_candidate)
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=encoded)
    if safe_candidate == DEFAULT_CANDIDATE_ID and write_legacy_for_local:
        s3.put_object(Bucket=bucket, Key=_legacy_provider_state_key(prefix, provider, profile), Body=encoded)


def build_state_payload(
    run_id: str,
    run_path: str,
    ended_at: Optional[str],
    providers: list[str],
    profiles: list[str],
    *,
    schema_version: int = 1,
    git_sha: Optional[str] = None,
    image_tag: Optional[str] = None,
) -> dict:
    payload = {
        "schema_version": schema_version,
        "run_id": run_id,
        "run_path": run_path,
        "ended_at": ended_at,
        "providers": providers,
        "profiles": profiles,
    }
    if git_sha:
        payload["git_sha"] = git_sha
    if image_tag:
        payload["image_tag"] = image_tag
    return payload


def download_baseline_ranked(
    bucket: str,
    prefix: str,
    run_id: str,
    provider: str,
    profile: str,
    dest_dir: Path,
    *,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    client=None,
) -> Optional[Path]:
    s3 = _get_client(client)
    safe_candidate = sanitize_candidate_id(candidate_id)
    if safe_candidate == DEFAULT_CANDIDATE_ID:
        key = f"{prefix.strip('/')}/runs/{run_id}/{provider}/{profile}/{provider}_ranked_jobs.{profile}.json".strip("/")
    else:
        key = (
            f"{prefix.strip('/')}/candidates/{safe_candidate}/runs/{run_id}/{provider}/{profile}/"
            f"{provider}_ranked_jobs.{profile}.json"
        ).strip("/")
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
    except Exception:
        return None
    body = resp.get("Body")
    if body is None:
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{provider}_ranked_jobs.{profile}.{run_id}.json"
    dest.write_bytes(body.read())
    return dest


def s3_enabled() -> bool:
    return os.environ.get("S3_PUBLISH_ENABLED", "0").strip() == "1"


def parse_pointer(payload: dict) -> Optional[str]:
    run_id = payload.get("run_id")
    run_path = payload.get("run_path")
    if isinstance(run_id, str) and run_id and isinstance(run_path, str) and run_path:
        return run_id
    return None


def now_iso() -> str:
    return utc_now_z(seconds_precision=True)


__all__ = [
    "BaselineInfo",
    "build_state_payload",
    "download_baseline_ranked",
    "get_most_recent_successful_run_id_before",
    "get_provider_last_success_state",
    "get_last_success_state",
    "get_most_recent_run_id_before",
    "now_iso",
    "parse_run_id_from_key",
    "parse_pointer",
    "read_last_success_state",
    "read_provider_last_success_state",
    "s3_enabled",
    "write_last_success_state",
    "write_provider_last_success_state",
]
