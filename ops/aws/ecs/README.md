# ECS Templates (SignalCraft)

This folder contains **templates only** for ECS scheduled runs. Replace placeholders before use.

## Files

- `taskdef.template.json` — ECS task definition outline
- `eventbridge-rule.template.json` — EventBridge schedule target
- `iam_policy_minimal.json` — least-privilege policy for S3 + logs

## Substitution guide

Replace the following placeholders:
- `<ACCOUNT_ID>` — AWS account ID
- `<AWS_REGION>` — region (e.g., `us-east-1`)
- `<CLUSTER_NAME>` — ECS cluster
- `<SECURITY_GROUP_ID>` — security group for task ENI
- `<SUBNET_ID_1>`, `<SUBNET_ID_2>` — subnets for task
- `<ECS_EXEC_ROLE>` / `<ECS_TASK_ROLE>` — IAM roles
- `<EVENTBRIDGE_ROLE>` — role for EventBridge to run tasks
- `<IMAGE_URI>` — image tag to run
- `<S3_BUCKET>` / `<BUCKET_NAME>` — S3 artifact bucket

## Notes

- Command defaults to deterministic, offline mode.
- Set `PUBLISH_S3=1` and `PUBLISH_S3_DRY_RUN=0` only when ready to publish.
- Keep secrets in SSM/Secrets Manager and map them into task env or inject via ECS secrets.
