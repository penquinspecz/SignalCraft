# DR Orchestrator: Auto-Detect -> Auto-Validate -> Manual Promote

Canonical operator entrypoint: `ops/dr/RUNBOOK_DISASTER_RECOVERY.md`.

## Scope

This design automates DR detection and validation, then pauses for manual promotion approval.

- Detect unhealthy batch state from S3 publish signals
- Mutate DR infrastructure in a controlled runner (CodeBuild), not in Lambda
- Validate k3s control plane on DR runner
- Notify operators and require manual approval token action
- Do **not** auto-promote

## Execution Model

Control plane:
- Step Functions state machine (phase orchestration)
- Lambda runner (decisioning, health checks, S3 contract checks, SSM validation, notifications)
- CodeBuild project (Terraform bringup/teardown mutation runner)

Data/receipts:
- S3 publish pointers and latest markers
- S3 receipt bundle per execution/phase

Terraform state:
- Remote S3 backend + DynamoDB lock for `ops/dr/terraform`
- Region/account explicit
- Orchestration path forbids local state

## Diagram (Text)

1. `check_health` (Lambda)
2. `should_run_dr` (Choice)
3. `bringup` (CodeBuild -> Terraform apply with remote backend)
4. `resolve_runner` (Lambda)
5. `restore` (Lambda backup contract check + control-plane bundle continuity apply before validation)
6. `validate` (Lambda -> SSM -> k3s checks)
7. `notify` (Lambda -> SNS)
8. `request_manual_approval` (Lambda + Step Functions callback token)
9. `promote` (Lambda decision record only; auto-promote disabled)
10. End (`approved_but_auto_promote_disabled` or `manual_promotion_rejected`)

Failure path:
- Any phase failure routes to `HandlePhaseFailure` -> `notify` with explicit `phase_name`, `failure_error`, `failure_reason` -> Fail state.

## Health Signals (Batch-First)

1. `pipeline freshness`
- Metric: `PipelineFreshnessHours`
- Unhealthy when no successful publish within `max_freshness_hours`
- Source pointer: `s3://<publish_bucket>/<publish_prefix>/state/last_success.json`

2. `publish correctness`
- Metric: `PublishCorrectness` (`0=ok`, `1=failed`)
- Unhealthy when pointer/marker contract fails:
  - `state/last_success.json`
  - `state/<provider>/<profile>/last_success.json`
  - `latest/<provider>/<profile>/<expected_marker_file>`

## Idempotency Contract

- `bringup`: idempotent
  - CodeBuild always applies desired Terraform state in remote backend.
- `restore`: idempotent
  - Re-validates required backup objects; no destructive mutation.
- `validate`: idempotent
  - Re-runs read-only k3s checks via SSM.
- `promote`: idempotent
  - Decision record only; repeated identical decisions are no-op from infra perspective.
- `teardown`: idempotent
  - CodeBuild runs Terraform destroy against the same remote backend state key.
  - Operated as an explicit/manual action (`ACTION=teardown`) and not auto-invoked by schedule.

## Trigger Safety

`enable_triggers` defaults to `false`:
- EventBridge schedule exists but is disabled
- CloudWatch alarms exist but actions are disabled

This prevents surprise auto-invocation during test rollout.

Use `enable_triggers=true` only after manual drill receipts and approval-path checks are verified.

## Deployment

```bash
cd ops/dr/orchestrator
terraform init
terraform plan \
  -var "region=us-east-1" \
  -var "expected_account_id=048622080012" \
  -var "publish_bucket=<publish-bucket>" \
  -var "publish_prefix=jobintel" \
  -var "backup_bucket=<backup-bucket>" \
  -var "backup_uri=s3://<backup-bucket>/<prefix>/backups/<backup_id>" \
  -var "receipt_bucket=<receipt-bucket>" \
  -var "receipt_prefix=jobintel/dr-orchestrator/receipts" \
  -var "notification_topic_arn=arn:aws:sns:us-east-1:048622080012:<topic>" \
  -var "dr_vpc_id=<vpc-id>" \
  -var "dr_subnet_id=<subnet-id>"
```

## Receipts

Each phase writes:

`s3://<receipt_bucket>/<receipt_prefix>/<execution_id>/<phase>.json`

CodeBuild bringup/teardown also writes:

`s3://<receipt_bucket>/<receipt_prefix>/<execution_id>/codebuild-<action>.json`

CloudWatch export for proof artifacts (token-safe):

```bash
scripts/ops/export_codebuild_cloudwatch_log_events.sh \
  --log-group-name /aws/codebuild/signalcraft-dr-orchestrator-dr-infra \
  --log-stream-name <codebuild-log-stream> \
  --output docs/proof/m19b-codebuild-cloudwatch-log-events-<timestamp>.json \
  --region us-east-1 \
  --expected-account-id 048622080012
```

`export_codebuild_cloudwatch_log_events.sh` preserves JSON shape and redacts
CloudWatch pagination token values (`nextForwardToken`, `nextBackwardToken`,
and other `next*Token` keys) so proof exports do not trip secret scanning.

Canonical receipt-bundle normalization + completeness check:

```bash
aws cloudwatch describe-alarm-history \
  --alarm-name signalcraft-dr-orchestrator-pipeline-freshness \
  --history-item-type StateUpdate \
  --max-records 50 \
  --region us-east-1 \
  --output json | jq '{AlarmHistoryItems: .AlarmHistoryItems}' \
  > docs/proof/m19b-alarm-history-pipeline-freshness-<timestamp>.json

aws cloudwatch describe-alarm-history \
  --alarm-name signalcraft-dr-orchestrator-publish-correctness \
  --history-item-type StateUpdate \
  --max-records 50 \
  --region us-east-1 \
  --output json | jq '{AlarmHistoryItems: .AlarmHistoryItems}' \
  > docs/proof/m19b-alarm-history-publish-correctness-<timestamp>.json

python3 scripts/ops/collect_dr_receipt_bundle.py \
  --source-dir docs/proof/receipts-m19b-success-true-<timestamp> \
  --output-dir docs/proof/receipt-bundle-m19b-success-true-<timestamp> \
  --alarm-history-json docs/proof/m19b-alarm-history-pipeline-freshness-<timestamp>.json \
  --alarm-history-json docs/proof/m19b-alarm-history-publish-correctness-<timestamp>.json

python3 scripts/ops/check_dr_receipt_bundle.py \
  --bundle-dir docs/proof/receipt-bundle-m19b-success-true-<timestamp>
```

`check_dr_receipt_bundle.py` fails closed when any required receipt is missing:
`check_health`, `bringup`, `restore`, `validate`, `notify`,
`request_manual_approval`, and alarm transition evidence showing `OK->ALARM->OK`.

## Manual Approval Operations

### Check orchestrator status

Use `dr_status.sh` to inspect latest execution or a specific execution:

```bash
scripts/ops/dr_status.sh \
  --state-machine-arn arn:aws:states:us-east-1:048622080012:stateMachine:signalcraft-dr-orchestrator-state-machine \
  --region us-east-1 \
  --expected-account-id 048622080012
```

```bash
scripts/ops/dr_status.sh \
  --execution-arn arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:<execution-id> \
  --region us-east-1 \
  --expected-account-id 048622080012
```

Output includes:
- latest/current execution status
- current phase
- failure reason (if present)
- receipt base S3 location

### How to promote

Use `dr_approve.sh` with execution ARN. It resolves the pending task token automatically and shows the approval summary:
- instance id
- image digest (if present in backup metadata)
- release metadata URI + compact metadata summary
- restore receipt URI

```bash
scripts/ops/dr_approve.sh \
  --execution-arn arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:<execution-id> \
  --region us-east-1 \
  --expected-account-id 048622080012 \
  --approver <name> \
  --ticket <change-ticket>
```

At prompt, answer `y` to approve. Script sends `send-task-success` directly.
Use `--dry-run` to verify token resolution and summary output without sending approval/rejection.

### How to reject

Run the same command. At prompt, answer anything other than `y`, then provide rejection reason.
Script sends `send-task-failure` with `error=ManualApprovalRejected` and your reason as `cause`.

### What happens next

- On approve: workflow enters `promote` phase, records decision, and ends at `approved_but_auto_promote_disabled`.
- On reject: workflow fails through the failure path, records rejection cause, and emits failure notification.
- In both cases, receipts remain under `s3://<receipt_bucket>/<receipt_prefix>/<execution_id>/`.

## Promote/Failback Semantics

Promotion and failback semantics are defined in `docs/dr_promote_failback.md`.
