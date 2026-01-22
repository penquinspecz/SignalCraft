# AWS Deployment (Smoke)

## Required env vars / secrets
- `JOBINTEL_S3_BUCKET` (required)
- `JOBINTEL_S3_PREFIX` (optional, default `jobintel`)
- `DISCORD_WEBHOOK_URL` (optional)
- `JOBINTEL_DASHBOARD_URL` (optional)
- `OPENAI_API_KEY` (optional; AI features)
- `AI_ENABLED` / `AI_JOB_BRIEFS_ENABLED` (optional)
- `S3_PUBLISH_ENABLED=1` (required for publish)
- `S3_PUBLISH_REQUIRE=1` (fail-closed; recommended for prod)

## First production run checklist
1. Set required env vars:
   - `JOBINTEL_S3_BUCKET`
   - `JOBINTEL_S3_PREFIX` (if not using default)
   - `S3_PUBLISH_ENABLED=1`
   - `S3_PUBLISH_REQUIRE=1`
   - `DISCORD_WEBHOOK_URL` (optional but recommended)
   - `JOBINTEL_DASHBOARD_URL` (optional)
2. Store secrets securely:
   - Prefer AWS SSM Parameter Store or Secrets Manager.
   - Pass secret ARNs via the Terraform `container_secrets` variable.
3. Verify IAM task role has S3 + CloudWatch logs permissions.
4. Run `make aws-smoke` and confirm bucket/prefix access.
5. Trigger a one-off task run and verify:
   - `runs/<run_id>/` uploaded
   - `latest/<provider>/<profile>/` updated
   - CloudWatch logs include a RUN SUMMARY block

## Deploy (Terraform)
```bash
cd ops/aws/infra
terraform init
terraform apply
```

## One-off task
Run the ECS task definition directly in the console or:
```bash
aws ecs run-task \
  --cluster <cluster-arn> \
  --task-definition jobintel-daily \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

## Verify S3 uploads
Expected keys:
- `s3://<bucket>/<prefix>/runs/<run_id>/...`
- `s3://<bucket>/<prefix>/latest/<provider>/<profile>/...`

Check:
```bash
aws s3 ls s3://<bucket>/<prefix>/runs/ --recursive | head
aws s3 ls s3://<bucket>/<prefix>/latest/ --recursive | head
```

## Smoke script
```bash
python scripts/aws_deploy_smoke.py --bucket <bucket> --prefix <prefix>
```
