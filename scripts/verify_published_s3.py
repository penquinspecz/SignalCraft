#!/usr/bin/env python3
from __future__ import annotations

try:
    import _bootstrap  # type: ignore
except ModuleNotFoundError:
    from scripts import _bootstrap  # noqa: F401

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import boto3
from botocore.exceptions import ClientError

from ji_engine.config import RUN_METADATA_DIR

try:
    from scripts import publish_s3  # type: ignore
except ModuleNotFoundError:
    import importlib.util

    _spec = importlib.util.spec_from_file_location(
        "publish_s3", Path(__file__).with_name("publish_s3.py")
    )
    if not _spec or not _spec.loader:
        raise
    publish_s3 = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(publish_s3)


def _run_dir(run_id: str) -> Path:
    return RUN_METADATA_DIR / publish_s3._sanitize_run_id(run_id)


def _load_run_report(run_id: str, run_dir: Path | None) -> Dict[str, Any]:
    run_dir = run_dir or _run_dir(run_id)
    report_path = run_dir / "run_report.json"
    if not report_path.exists():
        raise SystemExit(2)
    data = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(2)
    return data


def _collect_verifiable(report: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    verifiable = report.get("verifiable_artifacts")
    if not isinstance(verifiable, dict) or not verifiable:
        raise SystemExit(2)
    return verifiable


def _expected_keys(
    *,
    run_id: str,
    prefix: str,
    verifiable: Dict[str, Dict[str, str]],
    verify_latest: bool,
) -> Tuple[List[str], List[str]]:
    runs_keys: List[str] = []
    latest_keys: List[str] = []
    clean_prefix = prefix.strip("/")
    for logical_key, meta in verifiable.items():
        if not isinstance(meta, dict):
            raise SystemExit(2)
        path = meta.get("path")
        if not path:
            raise SystemExit(2)
        runs_key = f"{clean_prefix}/runs/{run_id}/{Path(path).as_posix()}".strip("/")
        runs_keys.append(runs_key)
        if not verify_latest:
            continue
        parsed = publish_s3._parse_logical_key(logical_key)
        if not parsed:
            continue
        provider, profile, output_key = parsed
        if output_key not in publish_s3.LATEST_OUTPUT_ALLOWLIST:
            continue
        latest_key = f"{clean_prefix}/latest/{provider}/{profile}/{Path(path).name}".strip("/")
        latest_keys.append(latest_key)
    runs_keys.sort()
    latest_keys.sort()
    return runs_keys, latest_keys


def _head_object(client, bucket: str, key: str, region: str | None) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify published S3 artifacts against run_report.json.")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prefix", default="jobintel")
    parser.add_argument("--region")
    parser.add_argument("--verify-latest", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)

    start = time.time()
    try:
        report = _load_run_report(args.run_id, None)
        verifiable = _collect_verifiable(report)
        runs_keys, latest_keys = _expected_keys(
            run_id=args.run_id,
            prefix=args.prefix,
            verifiable=verifiable,
            verify_latest=bool(args.verify_latest),
        )
        checked = {"runs": runs_keys, "latest": latest_keys}
        missing: List[str] = []
        if not args.offline:
            client = boto3.client("s3", region_name=args.region) if args.region else boto3.client("s3")
            for key in runs_keys:
                if not _head_object(client, args.bucket, key, args.region):
                    missing.append(key)
            for key in latest_keys:
                if not _head_object(client, args.bucket, key, args.region):
                    missing.append(key)
        ok = not missing
        payload = {
            "ok": ok,
            "missing": missing,
            "checked": checked,
            "elapsed_ms": int((time.time() - start) * 1000),
        }
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            if ok:
                print("OK: all expected objects found")
            else:
                print("MISSING:")
                for key in missing:
                    print(key)
        return 0 if ok else 2
    except SystemExit as exc:
        if args.json:
            payload = {
                "ok": False,
                "missing": [],
                "checked": {},
                "elapsed_ms": int((time.time() - start) * 1000),
            }
            print(json.dumps(payload, sort_keys=True))
        return 2 if exc.code in (None, 2) else int(exc.code)
    except Exception:
        if args.json:
            payload = {
                "ok": False,
                "missing": [],
                "checked": {},
                "elapsed_ms": int((time.time() - start) * 1000),
            }
            print(json.dumps(payload, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
