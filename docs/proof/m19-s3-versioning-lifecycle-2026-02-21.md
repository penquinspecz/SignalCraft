# M19 Proof: S3 Versioning + Lifecycle (Phase A)

Execution UTC: `2026-02-21T05:38:53Z`

## Scope
This receipt records live AWS evidence for Milestone 19 Phase A S3 hardening on the primary bucket.

## Execution Context
- Bucket: `jobintel-prod1`
- Prefix: `jobintel`
- Region: `us-east-1`
- Backup bucket: _not set_ (`JOBINTEL_S3_BACKUP_BUCKET` empty)

AWS caller identity:

```json
{
    "UserId": "048622080012",
    "Account": "048622080012",
    "Arn": "arn:aws:iam::048622080012:root"
}
```

## Commands Executed

```bash
aws sts get-caller-identity --output json

export JOBINTEL_S3_BUCKET=jobintel-prod1
export JOBINTEL_S3_PREFIX=jobintel
export AWS_REGION=us-east-1
# JOBINTEL_S3_BACKUP_BUCKET intentionally unset for this execution

echo "JOBINTEL_S3_BUCKET=$JOBINTEL_S3_BUCKET"
echo "JOBINTEL_S3_PREFIX=$JOBINTEL_S3_PREFIX"
echo "JOBINTEL_S3_BACKUP_BUCKET=${JOBINTEL_S3_BACKUP_BUCKET-}"
echo "AWS_REGION=$AWS_REGION"

make aws-s3-hardening
APPLY=1 make aws-s3-hardening

aws s3api get-bucket-versioning --bucket "$JOBINTEL_S3_BUCKET" --region "$AWS_REGION"
aws s3api get-bucket-lifecycle-configuration --bucket "$JOBINTEL_S3_BUCKET" --region "$AWS_REGION"
aws s3api get-bucket-encryption --bucket "$JOBINTEL_S3_BUCKET" --region "$AWS_REGION" || true
aws s3api get-public-access-block --bucket "$JOBINTEL_S3_BUCKET" --region "$AWS_REGION" || true
aws s3api get-bucket-replication --bucket "$JOBINTEL_S3_BUCKET" --region "$AWS_REGION" || true
```

## Raw Outputs

Environment echoes:

```text
JOBINTEL_S3_BUCKET=jobintel-prod1
JOBINTEL_S3_PREFIX=jobintel
JOBINTEL_S3_BACKUP_BUCKET=
AWS_REGION=us-east-1
```

`make aws-s3-hardening` (dry-run):

```json
{
  "backup_bucket": null,
  "mode": "dry-run",
  "ok": true,
  "prefix": "jobintel",
  "primary_bucket": "jobintel-prod1",
  "region": "us-east-1",
  "replication_strategy_note": "Preferred strategy: replicate immutable run artifacts from primary to backup bucket; retain latest/state pointers in primary and rebuild from runs during restore.",
  "results": [
    {
      "bucket": "jobintel-prod1",
      "lifecycle_action": "would_apply",
      "lifecycle_after": null,
      "lifecycle_before": null,
      "lifecycle_desired": {
        "Rules": [
          {
            "AbortIncompleteMultipartUpload": {
              "DaysAfterInitiation": 7
            },
            "Expiration": {
              "Days": 365
            },
            "Filter": {
              "Prefix": "jobintel/runs/"
            },
            "ID": "jobintel-runs-retention-v1",
            "NoncurrentVersionExpiration": {
              "NoncurrentDays": 180
            },
            "NoncurrentVersionTransitions": [
              {
                "NoncurrentDays": 30,
                "StorageClass": "STANDARD_IA"
              }
            ],
            "Status": "Enabled",
            "Transitions": [
              {
                "Days": 30,
                "StorageClass": "STANDARD_IA"
              }
            ]
          }
        ]
      },
      "lifecycle_matches_desired": false,
      "replication": {
        "rule_count": 0,
        "status": "not_configured"
      },
      "versioning_action": "would_enable",
      "versioning_after": "NotEnabled",
      "versioning_before": "NotEnabled"
    }
  ]
}
```

`APPLY=1 make aws-s3-hardening`:

```json
{
  "backup_bucket": null,
  "mode": "apply",
  "ok": true,
  "prefix": "jobintel",
  "primary_bucket": "jobintel-prod1",
  "region": "us-east-1",
  "replication_strategy_note": "Preferred strategy: replicate immutable run artifacts from primary to backup bucket; retain latest/state pointers in primary and rebuild from runs during restore.",
  "results": [
    {
      "bucket": "jobintel-prod1",
      "lifecycle_action": "applied",
      "lifecycle_after": {
        "Rules": [
          {
            "AbortIncompleteMultipartUpload": {
              "DaysAfterInitiation": 7
            },
            "Expiration": {
              "Days": 365
            },
            "Filter": {
              "Prefix": "jobintel/runs/"
            },
            "ID": "jobintel-runs-retention-v1",
            "NoncurrentVersionExpiration": {
              "NoncurrentDays": 180
            },
            "NoncurrentVersionTransitions": [
              {
                "NoncurrentDays": 30,
                "StorageClass": "STANDARD_IA"
              }
            ],
            "Status": "Enabled",
            "Transitions": [
              {
                "Days": 30,
                "StorageClass": "STANDARD_IA"
              }
            ]
          }
        ]
      },
      "lifecycle_before": null,
      "lifecycle_desired": {
        "Rules": [
          {
            "AbortIncompleteMultipartUpload": {
              "DaysAfterInitiation": 7
            },
            "Expiration": {
              "Days": 365
            },
            "Filter": {
              "Prefix": "jobintel/runs/"
            },
            "ID": "jobintel-runs-retention-v1",
            "NoncurrentVersionExpiration": {
              "NoncurrentDays": 180
            },
            "NoncurrentVersionTransitions": [
              {
                "NoncurrentDays": 30,
                "StorageClass": "STANDARD_IA"
              }
            ],
            "Status": "Enabled",
            "Transitions": [
              {
                "Days": 30,
                "StorageClass": "STANDARD_IA"
              }
            ]
          }
        ]
      },
      "lifecycle_matches_desired": false,
      "replication": {
        "rule_count": 0,
        "status": "not_configured"
      },
      "versioning_action": "enabled",
      "versioning_after": "Enabled",
      "versioning_before": "NotEnabled"
    }
  ]
}
```

`aws s3api get-bucket-versioning --bucket "jobintel-prod1" --region "us-east-1"`:

```json
{
    "Status": "Enabled"
}
```

`aws s3api get-bucket-lifecycle-configuration --bucket "jobintel-prod1" --region "us-east-1"`:

```json
{
    "TransitionDefaultMinimumObjectSize": "all_storage_classes_128K",
    "Rules": [
        {
            "Expiration": {
                "Days": 365
            },
            "ID": "jobintel-runs-retention-v1",
            "Filter": {
                "Prefix": "jobintel/runs/"
            },
            "Status": "Enabled",
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                }
            ],
            "NoncurrentVersionTransitions": [
                {
                    "NoncurrentDays": 30,
                    "StorageClass": "STANDARD_IA"
                }
            ],
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 180
            },
            "AbortIncompleteMultipartUpload": {
                "DaysAfterInitiation": 7
            }
        }
    ]
}
```

`aws s3api get-bucket-encryption --bucket "jobintel-prod1" --region "us-east-1"`:

```json
{
    "ServerSideEncryptionConfiguration": {
        "Rules": [
            {
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                },
                "BucketKeyEnabled": true
            }
        ]
    }
}
```

`aws s3api get-public-access-block --bucket "jobintel-prod1" --region "us-east-1"`:

```json
{
    "PublicAccessBlockConfiguration": {
        "BlockPublicAcls": true,
        "IgnorePublicAcls": true,
        "BlockPublicPolicy": true,
        "RestrictPublicBuckets": true
    }
}
```

`aws s3api get-bucket-replication --bucket "jobintel-prod1" --region "us-east-1"`:

```text
An error occurred (ReplicationConfigurationNotFoundError) when calling the GetBucketReplication operation: The replication configuration was not found
```

## Control Status
- Versioning: **PASS** (`Status=Enabled`)
- Lifecycle: **PASS** (rule `jobintel-runs-retention-v1` present and enabled)
- Encryption: **PASS** (SSE default configured: `AES256`)
- Public access block: **PASS** (all four block flags are `true`)
- Replication: **FAIL** (`ReplicationConfigurationNotFoundError` on primary bucket)

Replication rationale for Phase A: replication strategy is documented in `ops/aws/README.md`, but replication is not configured in this bucket yet.

Minimal remediation for replication gap:
1. Create/confirm backup bucket and destination policy.
2. Create IAM replication role + trust/policy.
3. Apply bucket replication configuration and re-run `get-bucket-replication` evidence capture.
