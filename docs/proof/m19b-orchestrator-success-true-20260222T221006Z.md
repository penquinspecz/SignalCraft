# M19B Orchestrator — True Success-Path Rehearsal (Attempt)

**Timestamp:** 2026-02-22T22:10:06Z  
**Outcome:** FAILED at bringup (CodeBuild quota blocker)  
**No infra leak:** Confirmed — no EC2 runners created  

## Execution ARN

```
arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260222T220931Z
```

## Target Chain (Not Achieved)

check_health → bringup → restore → validate → request_manual_approval → record_manual_decision → notify (SUCCESS)

## Actual Outcome

| Phase | Status | Receipt URI |
|-------|--------|-------------|
| check_health | SUCCESS | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260222T220931Z/check_health.json` |
| bringup | FAILED | (no receipt — failed before CodeBuild start) |
| restore | not reached | — |
| validate | not reached | — |
| request_manual_approval | not reached | — |
| record_manual_decision | not reached | — |
| notify | SUCCESS (failure notification) | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260222T220931Z/notify.json` |

## Failure Diagnosis

**Error:** `CodeBuild.AccountLimitExceededException: Cannot have more than 0 builds in queue for the account`

**Root cause:** AWS account-level CodeBuild queue/concurrent limit appears to be 0 despite Service Quotas showing Linux/Medium (L-2DC20C30) = 10.

**Verification:**
- `aws service-quotas get-service-quota --service-code codebuild --quota-code L-2DC20C30 --region us-east-1` → Value: 10
- CodeBuild project `signalcraft-dr-orchestrator-dr-infra` uses `LINUX_CONTAINER` + `BUILD_GENERAL1_MEDIUM` (Linux/Medium)
- Error persists on start-build

**Likely causes:**
1. Internal AWS metrics differ from Service Quotas (per [limits docs](https://docs.aws.amazon.com/codebuild/latest/userguide/limits.html): "Internal metrics will determine the default quotas")
2. New/lower-usage account with conservative internal limit
3. Quota increase not yet propagated

**Remediation (not code):**
- Open AWS Support case under "Account and billing" (free)
- Request CodeBuild concurrent build quota increase for Linux/Medium (L-2DC20C30)
- Or use `aws service-quotas request-service-quota-increase` if allowed

## IMAGE_REF (digest-pinned)

```
048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:b33a382bca2456df8a4f8a0343f10c63503dbbbb44f45bf1be5a0684ef2e05b7
```

(From m19 release; backup metadata does not include image_ref_digest.)

## Cost Notes

- Lambda: check_health, notify (failure path)
- CodeBuild: 0 (build never started)
- EC2: 0 (bringup failed before terraform apply)
- SNS: 1 notification

## Teardown Confirmation

- No EC2 runners created (bringup failed before terraform apply)
- `aws ec2 describe-instances` for `jobintel-dr-runner` + `jobintel-dr`: 0 instances

## Artifacts

| Artifact | Path |
|----------|------|
| Execution history | `docs/proof/m19b-success-execution-history-20260222T220931Z.json` |
| check_health receipt | `docs/proof/receipts-m19b-success-true-20260222T220931Z/check_health.json` |
| notify receipt | `docs/proof/receipts-m19b-success-true-20260222T220931Z/notify.json` |

## Retry After Quota Fix

```bash
export PUBLISH_BUCKET=jobintel-prod1
export BACKUP_URI=s3://jobintel-prod1/jobintel/backups/backup-20260221T061624Z
export RECEIPT_BUCKET=jobintel-prod1
export NOTIFICATION_TOPIC_ARN=arn:aws:sns:us-east-1:048622080012:signalcraft-dr-notifications
export DR_VPC_ID=vpc-4362fc3e
export DR_SUBNET_ID=subnet-11001d5c

./scripts/ops/dr_trigger.sh --name "m19b-success-true-$(date -u +%Y%m%dT%H%M%SZ)"

# When at request_manual_approval:
./scripts/ops/dr_approve.sh --execution-arn <arn> --approver <name> --ticket <id> --yes
```
