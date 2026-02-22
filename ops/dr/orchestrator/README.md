# DR Orchestrator Terraform

This module provisions a deterministic DR orchestrator for SignalCraft.
Canonical operator flow/runbook: `ops/dr/RUNBOOK_DISASTER_RECOVERY.md`.

Execution split:
- Step Functions + Lambda: orchestration, health checks, restore contract checks, validation, notify/manual gate
- CodeBuild: infrastructure mutation (`bringup`/`teardown`) via Terraform only

## Hardening Guarantees

- No Terraform execution in Lambda
- DR Terraform uses remote backend (`s3` + DynamoDB lock)
- Region/account explicit checks enforced
- Phase receipts are written to S3 for every run
- Triggers are safe-by-default (`enable_triggers=false`)

## Required inputs

- `expected_account_id`
- `publish_bucket`
- `backup_bucket`
- `backup_uri`
- `receipt_bucket`
- `notification_topic_arn`
- `dr_vpc_id`
- `dr_subnet_id`

## Quick start

```bash
cd ops/dr/orchestrator
terraform init
terraform apply \
  -var "region=us-east-1" \
  -var "expected_account_id=048622080012" \
  -var "publish_bucket=<bucket>" \
  -var "publish_prefix=jobintel" \
  -var "backup_bucket=<bucket>" \
  -var "backup_uri=s3://<bucket>/<prefix>/backups/<backup_id>" \
  -var "receipt_bucket=<bucket>" \
  -var "receipt_prefix=jobintel/dr-orchestrator/receipts" \
  -var "notification_topic_arn=arn:aws:sns:us-east-1:048622080012:<topic>" \
  -var "dr_vpc_id=<vpc-id>" \
  -var "dr_subnet_id=<subnet-id>"
```

## Manual approval gate

During `request_manual_approval`, SNS includes tokenized approve/reject command examples.

Operator helpers:

```bash
scripts/ops/dr_status.sh \
  --state-machine-arn arn:aws:states:us-east-1:048622080012:stateMachine:signalcraft-dr-orchestrator-state-machine \
  --region us-east-1 \
  --expected-account-id 048622080012
```

```bash
scripts/ops/dr_approve.sh \
  --execution-arn arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:<execution-id> \
  --region us-east-1 \
  --expected-account-id 048622080012 \
  --approver <name> \
  --ticket <change-ticket>
```

## Receipts

- Lambda phases: `s3://<receipt_bucket>/<receipt_prefix>/<execution_id>/<phase>.json`
- CodeBuild phases: `s3://<receipt_bucket>/<receipt_prefix>/<execution_id>/codebuild-<action>.json`
