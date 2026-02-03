# ECS Proof Run Checklist (Milestone 2)

This checklist is for a **one-time, real ECS run** that proves the pipeline runs
end-to-end and publishes deterministic artifacts. It is **copy/pasteable** and
designed to produce proof artifacts for the PR.

## Prereqs
- AWS CLI configured (or assumed role) with access to ECR, ECS, EventBridge, S3.
- ECR image pushed for this repo.
- S3 bucket exists for publish targets.
- Discord webhook (optional).

Set these placeholders first:

```bash
export AWS_REGION="<region>"
export AWS_ACCOUNT_ID="<account_id>"
export ECR_REPO="<ecr_repo_name>"
export IMAGE_TAG="<image_tag>"
export CLUSTER_NAME="<ecs_cluster>"
export SUBNETS="<subnet-1>,<subnet-2>"
export SECURITY_GROUPS="<sg-1>"
export LOG_GROUP="/aws/ecs/jobintel"
export BUCKET="<s3_bucket>"
export PREFIX="jobintel"
```

## 1) Push image to ECR

```bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker tag jobintel:latest "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"
```

## 2) Register task definition

Copy `ops/aws/ecs/taskdef.template.json`, replace placeholders, then:

```bash
aws ecs register-task-definition \
  --region "$AWS_REGION" \
  --cli-input-json file://taskdef.json
```

## 3) Run task once

```bash
aws ecs run-task \
  --region "$AWS_REGION" \
  --cluster "$CLUSTER_NAME" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUPS],assignPublicIp=ENABLED}" \
  --task-definition jobintel
```

## 4) Fetch logs

```bash
aws logs tail "$LOG_GROUP" --since 10m --follow
```

## Expected outputs (proof artifacts)
- A CloudWatch log line containing `run_id=...`.
- A run report JSON path logged (includes `verifiable_artifacts`).
- Publish plan JSON (from `publish_s3 --plan --json` or stored plan file).
- Offline verify JSON from `verify_published_s3 --offline --plan-json ...` showing `"ok": true`.
- S3 keys under:
  - `runs/<run_id>/...`
  - `latest/<provider>/<profile>/...`

## Proof snippet (local extraction)

Use the local extractor against the run report and plan JSON:

```bash
python scripts/proof_run_extract.py \
  --run-report /path/to/run_report.json \
  --plan-json /path/to/publish_plan.json
```

