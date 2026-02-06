#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class S3Location:
    bucket: str
    key_prefix: str


def parse_s3_uri(uri: str) -> S3Location:
    if not uri.startswith("s3://"):
        raise ValueError("backup uri must start with s3://")
    payload = uri[len("s3://") :]
    if "/" not in payload:
        raise ValueError("backup uri must include bucket and key prefix")
    bucket, prefix = payload.split("/", 1)
    prefix = prefix.strip("/")
    if not bucket or not prefix:
        raise ValueError("backup uri bucket/prefix is empty")
    return S3Location(bucket=bucket, key_prefix=prefix)


def required_backup_keys(location: S3Location) -> list[str]:
    return [
        f"{location.key_prefix}/metadata.json",
        f"{location.key_prefix}/state.tar.zst",
        f"{location.key_prefix}/manifests.tar.zst",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DR backup contract helper")
    parser.add_argument("--backup-uri", required=True, help="s3://bucket/prefix/backups/<backup_id>")
    args = parser.parse_args(argv)

    location = parse_s3_uri(args.backup_uri)
    payload = {
        "bucket": location.bucket,
        "required_keys": required_backup_keys(location),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
