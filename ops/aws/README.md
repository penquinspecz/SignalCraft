# AWS Deployment (Milestone 2)

## Minimal IAM policy (least privilege)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "JobIntelS3Publish",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR_BUCKET_NAME",
        "arn:aws:s3:::YOUR_BUCKET_NAME/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

## ECS task definition (outline)
- Image: `jobintel:latest`
- Command: `python scripts/run_daily.py --profiles cs --providers openai --no_post`
- Environment:
  - `JOBINTEL_S3_BUCKET`
  - `JOBINTEL_S3_PREFIX` (optional)
  - `PUBLISH_S3=1`
  - `PUBLISH_S3_DRY_RUN=1` (optional)
  - `DISCORD_WEBHOOK_URL` (optional)
  - `JOBINTEL_DASHBOARD_URL` (optional)
  - `OPENAI_API_KEY` (optional)
- Logging: CloudWatch Logs (awslogs driver)

## EventBridge schedule
- Rule: cron or rate (e.g., `rate(7 days)` for weekly)
- Target: ECS task (same task definition)

## Secrets / env vars
- `DISCORD_WEBHOOK_URL` (Discord alerts + summaries)
- `JOBINTEL_S3_BUCKET` (required for S3 publishing)
- `JOBINTEL_S3_PREFIX` (optional; default `jobintel`)
- `JOBINTEL_DASHBOARD_URL` (optional; used for links)
- `OPENAI_API_KEY` (optional; AI-enabled paths)
- `AI_ENABLED=1` (optional; for AI insights)
- `PUBLISH_S3=1` (publish run artifacts to S3)
- `PUBLISH_S3_DRY_RUN=1` (log-only publishing)

## S3 layout
Run artifacts and pointers are published under deterministic keys:
- `s3://<bucket>/<prefix>/runs/<run_id>/...` (full run artifacts)
- `s3://<bucket>/<prefix>/latest/<provider>/<profile>/...` (latest per provider/profile)
- `s3://<bucket>/<prefix>/state/last_success.json` (global pointer)
- `s3://<bucket>/<prefix>/state/<provider>/<profile>/last_success.json` (provider/profile pointer)

## Retention strategy
- Keep full run artifacts under `runs/<run_id>/` for as long as required by compliance.
- `latest/` keys and `state/last_success.json` are overwritten each successful run.

## Verify publish
```bash
aws s3 ls "s3://$JOBINTEL_S3_BUCKET/$JOBINTEL_S3_PREFIX/runs/<run_id>/"
aws s3 ls "s3://$JOBINTEL_S3_BUCKET/$JOBINTEL_S3_PREFIX/latest/openai/cs/"
aws s3 cp "s3://$JOBINTEL_S3_BUCKET/$JOBINTEL_S3_PREFIX/state/last_success.json" -
aws s3 cp "s3://$JOBINTEL_S3_BUCKET/$JOBINTEL_S3_PREFIX/state/last_success.json" - | jq -r '.run_id'
```

## CloudWatch logging basics
- Ensure `awslogs-group` and `awslogs-stream-prefix` are set in the task.
- Verify logs in CloudWatch: `/ecs/jobintel` (or your group).

## Quick runbook
1. Validate env vars:
   - `make aws-env-check`
2. Run once:
   - `S3_PUBLISH_ENABLED=1 make daily`
3. Publish an existing run:
   - `make publish-last RUN_ID=<run_id>`
