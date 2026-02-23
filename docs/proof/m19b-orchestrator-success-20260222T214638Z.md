# M19B Orchestrator Rehearsal — Partial Success (2026-02-22)

Orchestrator deployment and execution attempted. Full success-path blocked by CodeBuild account quota.

## Summary

- **Orchestrator deployed:** Step Functions state machine, Lambda, CodeBuild, SNS, EventBridge
- **Execution started:** `m19b-success-20260222T214638Z` with `force_run=true`
- **Phases completed:** check_health (SUCCESS), ShouldRunDR (proceed)
- **Phase failed:** bringup (CodeBuild.AccountLimitExceededException)
- **Failure handling:** HandlePhaseFailure → notify (SNS) → FailWorkflow

## Execution ARN

```
arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-20260222T214638Z
```

## Receipt URIs (S3)

| Phase | URI |
|-------|-----|
| check_health | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-20260222T214638Z/check_health.json` |
| notify | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-20260222T214638Z/notify.json` |
| bringup | (failed before receipt) |
| restore | (not reached) |
| validate | (not reached) |
| request_manual_approval | (not reached) |
| record_manual_decision | (not reached) |

## Local Artifacts (docs/proof)

- `m19b-orchestrator-execution-history-20260222T214638Z.json` — Step Functions execution history export
- `m19b-orchestrator-check_health-20260222T214638Z.json` — check_health receipt copy
- `m19b-orchestrator-notify-20260222T214638Z.json` — notify receipt copy

## IMAGE_REF (backup context)

Backup used: `s3://jobintel-prod1/jobintel/backups/backup-20260221T061624Z`

Reference digest from latest m19 release: `048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:b33a382bca2456df8a4f8a0343f10c63503dbbbb44f45bf1be5a0684ef2e05b7`

## Cost Notes

- Orchestrator Terraform: S3 (tfstate), DynamoDB (lock), Lambda, CodeBuild project, Step Functions, EventBridge, CloudWatch alarms, SNS topic
- Execution: check_health (Lambda), bringup attempt (CodeBuild — failed at queue), notify (Lambda + SNS)
- No EC2/CodeBuild compute consumed (bringup failed before build start)

## Fixes Applied (PR-worthy)

1. **Lambda AWS_REGION:** Removed reserved `AWS_REGION` env var from Lambda; region passed via event payload.
2. **SFN EventBridge managed-rule:** Added `events:PutRule`, `events:PutTargets`, `events:DescribeRule` to SFN IAM role for CodeBuild `.sync` pattern.
3. **DynamoDB import:** Existing `signalcraft-dr-tf-lock` table imported into Terraform state.

## Blocker

`CodeBuild.AccountLimitExceededException: Cannot have more than 0 builds in queue for the account`

Account-level CodeBuild quota (concurrent builds) appears to be 0. Request quota increase via AWS Service Quotas or contact AWS Support.

## Retry Instructions

When CodeBuild quota allows:

```bash
# 1. Build input with force_run=true (use tmp_dr_exec_input.json or equivalent)
# 2. Start execution
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:048622080012:stateMachine:signalcraft-dr-orchestrator-state-machine" \
  --name "m19b-success-$(date -u +%Y%m%dT%H%M%SZ)" \
  --input file://tmp_dr_exec_input.json \
  --region us-east-1

# 3. Monitor
scripts/ops/dr_status.sh --execution-arn <execution-arn> --region us-east-1

# 4. When at request_manual_approval, approve
scripts/ops/dr_approve.sh --execution-arn <execution-arn> --approver <name> --ticket <id> --yes
```

## Manual Trigger Script

`scripts/ops/dr_trigger.sh` — wraps `aws stepfunctions start-execution` with force_run=true and required env vars. See script usage for PUBLISH_BUCKET, BACKUP_URI, RECEIPT_BUCKET, NOTIFICATION_TOPIC_ARN, DR_VPC_ID, DR_SUBNET_ID.
