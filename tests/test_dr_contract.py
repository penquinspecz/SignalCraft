from __future__ import annotations

import pytest

from scripts.ops.dr_contract import S3Location, parse_s3_uri, required_backup_keys


def test_parse_s3_uri_parses_bucket_and_prefix() -> None:
    loc = parse_s3_uri("s3://bucket-a/jobintel/backups/20260206T120000Z")
    assert loc == S3Location(bucket="bucket-a", key_prefix="jobintel/backups/20260206T120000Z")


def test_parse_s3_uri_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        parse_s3_uri("https://example.com")
    with pytest.raises(ValueError):
        parse_s3_uri("s3://bucket-only")


def test_required_backup_keys_are_deterministic() -> None:
    loc = S3Location(bucket="bucket-a", key_prefix="jobintel/backups/run-1")
    assert required_backup_keys(loc) == [
        "jobintel/backups/run-1/metadata.json",
        "jobintel/backups/run-1/state.tar.zst",
        "jobintel/backups/run-1/manifests.tar.zst",
    ]
