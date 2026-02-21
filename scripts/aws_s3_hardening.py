#!/usr/bin/env python3
from __future__ import annotations

try:
    import _bootstrap  # type: ignore
except ModuleNotFoundError:
    from scripts import _bootstrap  # noqa: F401

import argparse
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PREFIX = "jobintel"
_AWS_ERR_CODE_RE = re.compile(r"\(([A-Za-z0-9_]+)\)")


@dataclass(frozen=True)
class BucketPlan:
    name: str
    lifecycle: dict[str, Any] | None


class AwsCliError(RuntimeError):
    def __init__(self, *, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


def _resolve_bucket(explicit: str | None, *, env_keys: tuple[str, ...]) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    for key in env_keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return None


def _resolve_region(explicit: str | None) -> str | None:
    value = (
        explicit or os.getenv("JOBINTEL_AWS_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or ""
    ).strip()
    return value or None


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _same_payload(a: Any, b: Any) -> bool:
    return _canonical(a) == _canonical(b)


def _error_code(stderr: str) -> str | None:
    match = _AWS_ERR_CODE_RE.search(stderr)
    if not match:
        return None
    return match.group(1)


def _aws(args: list[str], *, region: str | None, expect_json: bool) -> Any:
    cmd = ["aws", *args]
    if region:
        cmd.extend(["--region", region])
    if expect_json:
        cmd.extend(["--output", "json"])
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise AwsCliError(message=stderr or "aws cli failed", code=_error_code(stderr))
    if not expect_json:
        return None
    body = (result.stdout or "").strip()
    if not body:
        return {}
    return json.loads(body)


def _build_primary_lifecycle(prefix: str) -> dict[str, Any]:
    clean = prefix.strip("/") or DEFAULT_PREFIX
    runs_prefix = f"{clean}/runs/"
    return {
        "Rules": [
            {
                "ID": "jobintel-runs-retention-v1",
                "Status": "Enabled",
                "Filter": {"Prefix": runs_prefix},
                "Transitions": [{"Days": 30, "StorageClass": "STANDARD_IA"}],
                "Expiration": {"Days": 365},
                "NoncurrentVersionTransitions": [{"NoncurrentDays": 30, "StorageClass": "STANDARD_IA"}],
                "NoncurrentVersionExpiration": {"NoncurrentDays": 180},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            }
        ]
    }


def _build_backup_lifecycle(prefix: str) -> dict[str, Any]:
    clean = prefix.strip("/") or DEFAULT_PREFIX
    backups_prefix = f"{clean}/backups/"
    return {
        "Rules": [
            {
                "ID": "jobintel-backups-retention-v1",
                "Status": "Enabled",
                "Filter": {"Prefix": backups_prefix},
                "Transitions": [{"Days": 60, "StorageClass": "GLACIER_IR"}],
                "Expiration": {"Days": 730},
                "NoncurrentVersionTransitions": [{"NoncurrentDays": 30, "StorageClass": "GLACIER_IR"}],
                "NoncurrentVersionExpiration": {"NoncurrentDays": 365},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            }
        ]
    }


def _head_bucket(bucket: str, *, region: str | None) -> None:
    _aws(["s3api", "head-bucket", "--bucket", bucket], region=region, expect_json=False)


def _get_bucket_versioning(bucket: str, *, region: str | None) -> str:
    response = _aws(["s3api", "get-bucket-versioning", "--bucket", bucket], region=region, expect_json=True)
    return str(response.get("Status") or "NotEnabled")


def _put_bucket_versioning(bucket: str, *, region: str | None) -> None:
    _aws(
        [
            "s3api",
            "put-bucket-versioning",
            "--bucket",
            bucket,
            "--versioning-configuration",
            "Status=Enabled",
        ],
        region=region,
        expect_json=False,
    )


def _get_lifecycle(bucket: str, *, region: str | None) -> dict[str, Any] | None:
    try:
        response = _aws(
            ["s3api", "get-bucket-lifecycle-configuration", "--bucket", bucket],
            region=region,
            expect_json=True,
        )
    except AwsCliError as exc:
        if exc.code in {"NoSuchLifecycleConfiguration", "NoSuchLifecycle"}:
            return None
        raise
    return {"Rules": response.get("Rules") or []}


def _put_lifecycle(bucket: str, lifecycle: dict[str, Any], *, region: str | None) -> None:
    with tempfile.TemporaryDirectory(prefix="jobintel-m19-") as tmp_dir:
        payload_path = Path(tmp_dir) / "lifecycle.json"
        payload_path.write_text(json.dumps(lifecycle, sort_keys=True) + "\n", encoding="utf-8")
        _aws(
            [
                "s3api",
                "put-bucket-lifecycle-configuration",
                "--bucket",
                bucket,
                "--lifecycle-configuration",
                f"file://{payload_path}",
            ],
            region=region,
            expect_json=False,
        )


def _get_replication_status(bucket: str, *, region: str | None) -> dict[str, Any]:
    try:
        response = _aws(["s3api", "get-bucket-replication", "--bucket", bucket], region=region, expect_json=True)
    except AwsCliError as exc:
        if exc.code in {"ReplicationConfigurationNotFoundError", "NoSuchReplicationConfiguration"}:
            return {"status": "not_configured", "rule_count": 0}
        return {
            "status": "error",
            "error_code": exc.code,
            "message": str(exc),
        }

    replication = response.get("ReplicationConfiguration") or {}
    rules = replication.get("Rules") or []
    return {
        "status": "configured",
        "rule_count": len(rules),
        "role": replication.get("Role"),
    }


def _apply_bucket_plan(*, plan: BucketPlan, region: str | None, apply: bool) -> dict[str, Any]:
    _head_bucket(plan.name, region=region)

    versioning_before = _get_bucket_versioning(plan.name, region=region)
    if versioning_before == "Enabled":
        versioning_action = "none"
    elif apply:
        _put_bucket_versioning(plan.name, region=region)
        versioning_action = "enabled"
    else:
        versioning_action = "would_enable"
    versioning_after = _get_bucket_versioning(plan.name, region=region)

    lifecycle_before = _get_lifecycle(plan.name, region=region)
    lifecycle_after = lifecycle_before
    lifecycle_action = "none"
    lifecycle_matches = True
    if plan.lifecycle is not None:
        lifecycle_matches = _same_payload(lifecycle_before or {"Rules": []}, plan.lifecycle)
        if not lifecycle_matches:
            if apply:
                _put_lifecycle(plan.name, plan.lifecycle, region=region)
                lifecycle_action = "applied"
            else:
                lifecycle_action = "would_apply"
            lifecycle_after = _get_lifecycle(plan.name, region=region)

    return {
        "bucket": plan.name,
        "versioning_before": versioning_before,
        "versioning_action": versioning_action,
        "versioning_after": versioning_after,
        "lifecycle_before": lifecycle_before,
        "lifecycle_action": lifecycle_action,
        "lifecycle_after": lifecycle_after,
        "lifecycle_desired": plan.lifecycle,
        "lifecycle_matches_desired": lifecycle_matches,
        "replication": _get_replication_status(plan.name, region=region),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M19 Phase A S3 hardening: versioning + lifecycle (idempotent).")
    parser.add_argument("--bucket", default=None, help="Primary artifacts bucket (env: JOBINTEL_S3_BUCKET).")
    parser.add_argument(
        "--backup-bucket",
        default=None,
        help="Backup bucket for DR artifacts (env: JOBINTEL_S3_BACKUP_BUCKET).",
    )
    parser.add_argument("--prefix", default=None, help=f"Artifact key prefix (default: {DEFAULT_PREFIX}).")
    parser.add_argument("--region", default=None, help="AWS region override.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Omit for dry-run.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    primary_bucket = _resolve_bucket(args.bucket, env_keys=("JOBINTEL_S3_BUCKET", "BUCKET"))
    backup_bucket = _resolve_bucket(args.backup_bucket, env_keys=("JOBINTEL_S3_BACKUP_BUCKET",))
    prefix = (args.prefix or os.getenv("JOBINTEL_S3_PREFIX") or os.getenv("PREFIX") or DEFAULT_PREFIX).strip(
        "/"
    ) or DEFAULT_PREFIX
    region = _resolve_region(args.region)

    if not primary_bucket:
        payload = {
            "ok": False,
            "error": "missing required bucket (set JOBINTEL_S3_BUCKET or --bucket)",
        }
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print(payload["error"], file=sys.stderr)
        return 2

    try:
        plans: list[BucketPlan] = [
            BucketPlan(name=primary_bucket, lifecycle=_build_primary_lifecycle(prefix)),
        ]
        if backup_bucket:
            plans.append(BucketPlan(name=backup_bucket, lifecycle=_build_backup_lifecycle(prefix)))

        results = [_apply_bucket_plan(plan=plan, region=region, apply=bool(args.apply)) for plan in plans]
        payload = {
            "ok": True,
            "mode": "apply" if args.apply else "dry-run",
            "region": region,
            "prefix": prefix,
            "primary_bucket": primary_bucket,
            "backup_bucket": backup_bucket,
            "results": results,
            "replication_strategy_note": (
                "Preferred strategy: replicate immutable run artifacts from primary to backup bucket; "
                "retain latest/state pointers in primary and rebuild from runs during restore."
            ),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "apply" if args.apply else "dry-run",
            "region": region,
            "prefix": prefix,
            "primary_bucket": primary_bucket,
            "backup_bucket": backup_bucket,
            "error": str(exc),
        }

    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))

    return 0 if payload.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
