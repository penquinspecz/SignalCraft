# M19 Proof: S3 Versioning + Lifecycle (Phase A)

Date: 2026-02-21

## Scope
Milestone 19 Phase A implementation:
- idempotent versioning enablement path
- idempotent lifecycle policy application path
- backup bucket replication strategy documented

Code paths:
- `scripts/aws_s3_hardening.py`
- `Makefile` target `aws-s3-hardening`
- `ops/aws/README.md` (bucket roles, retention semantics, replication strategy)
- `docs/OPS_RUNBOOK.md` (operator command path)

## Commands Executed

```bash
# Attempt dry-run path (primary bucket example from ops docs)
JOBINTEL_S3_BUCKET=jobintel-prod1 JOBINTEL_S3_PREFIX=jobintel make aws-s3-hardening

# Attempt apply path (same bucket)
JOBINTEL_S3_BUCKET=jobintel-prod1 JOBINTEL_S3_PREFIX=jobintel APPLY=1 make aws-s3-hardening

# Explicit validation commands required by M19 receipt contract
aws s3api get-bucket-versioning --bucket jobintel-prod1
aws s3api get-bucket-lifecycle-configuration --bucket jobintel-prod1
```

## Command Outputs

`make aws-s3-hardening` (dry-run):

```text
{
  "backup_bucket": null,
  "error": "Your session has expired. Please reauthenticate using 'aws login'.",
  "mode": "dry-run",
  "ok": false,
  "prefix": "jobintel",
  "primary_bucket": "jobintel-prod1",
  "region": null
}
make: *** [aws-s3-hardening] Error 3
```

`make aws-s3-hardening` (apply):

```text
{
  "backup_bucket": null,
  "error": "Your session has expired. Please reauthenticate using 'aws login'.",
  "mode": "apply",
  "ok": false,
  "prefix": "jobintel",
  "primary_bucket": "jobintel-prod1",
  "region": null
}
make: *** [aws-s3-hardening] Error 3
```

`aws s3api get-bucket-versioning --bucket jobintel-prod1`:

```text
Your session has expired. Please reauthenticate using 'aws login'.
```

`aws s3api get-bucket-lifecycle-configuration --bucket jobintel-prod1`:

```text
Your session has expired. Please reauthenticate using 'aws login'.
```

## Pass/Fail Status
- Implementation status: **PASS** (script + make + docs landed)
- Live AWS evidence status: **BLOCKED** (expired AWS session in this execution environment)

## Deterministic Re-run (after AWS re-auth)

```bash
aws login
JOBINTEL_S3_BUCKET=<primary-bucket> JOBINTEL_S3_PREFIX=jobintel JOBINTEL_S3_BACKUP_BUCKET=<backup-bucket> APPLY=1 make aws-s3-hardening
aws s3api get-bucket-versioning --bucket <primary-bucket>
aws s3api get-bucket-lifecycle-configuration --bucket <primary-bucket>
aws s3api get-bucket-versioning --bucket <backup-bucket>
aws s3api get-bucket-lifecycle-configuration --bucket <backup-bucket>
```

Expected success criteria after re-auth:
- versioning `Status` is `Enabled` for both buckets
- lifecycle rules exist with IDs:
  - `jobintel-runs-retention-v1` on primary
  - `jobintel-backups-retention-v1` on backup (if configured)
