#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   CLUSTER_ARN=... TASK_ARN=... REGION=us-east-1 ./scripts/ecs_verify_task.sh
#   EXPECT_IMAGE_SUBSTR=jobintel ./scripts/ecs_verify_task.sh --cluster ... --task ... --region us-east-1

CLUSTER_ARN="${CLUSTER_ARN:-}"
TASK_ARN="${TASK_ARN:-}"
REGION="${REGION:-${AWS_REGION:-us-east-1}}"
EXPECT_IMAGE_SUBSTR="${EXPECT_IMAGE_SUBSTR:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster) CLUSTER_ARN="$2"; shift 2 ;;
    --task) TASK_ARN="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --expect-image) EXPECT_IMAGE_SUBSTR="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
 done

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required" >&2
  exit 2
fi

if [[ -z "${CLUSTER_ARN}" || -z "${TASK_ARN}" ]]; then
  echo "CLUSTER_ARN and TASK_ARN are required." >&2
  exit 2
fi

resp=$(aws ecs describe-tasks --cluster "${CLUSTER_ARN}" --tasks "${TASK_ARN}" --region "${REGION}")

task_def_arn=$(python - <<PY
import json
import sys

data=json.loads("""${resp}""")
print(data.get("tasks", [{}])[0].get("taskDefinitionArn", ""))
PY
)

python - <<PY
import json

data=json.loads("""${resp}""")

task=data.get("tasks", [{}])[0]
print("lastStatus:", task.get("lastStatus"))
print("stoppedReason:", task.get("stoppedReason"))
for container in task.get("containers", []):
    print("container:", container.get("name"))
    print("  exitCode:", container.get("exitCode"))
    print("  image:", container.get("image"))
    print("  imageDigest:", container.get("imageDigest"))
PY

if [[ -z "${task_def_arn}" ]]; then
  echo "Unable to resolve task definition ARN." >&2
  exit 3
fi

taskdef=$(aws ecs describe-task-definition --task-definition "${task_def_arn}" --region "${REGION}")

python - <<PY
import json

payload=json.loads("""${taskdef}""")
container=payload.get("taskDefinition", {}).get("containerDefinitions", [{}])[0]
print("taskDefinition:", payload.get("taskDefinition", {}).get("taskDefinitionArn"))
print("image:", container.get("image"))
print("environment:")
wanted={"S3_PUBLISH_ENABLED","S3_PUBLISH_REQUIRE","JOBINTEL_S3_BUCKET","JOBINTEL_S3_PREFIX"}
found=set()
for env in container.get("environment", []):
    name=env.get("name")
    if name in wanted:
        print(f"  {name}={env.get('value')}")
        found.add(name)
missing=sorted(wanted - found)
if missing:
    print("WARNING: missing env vars:", ", ".join(missing))
PY

if [[ -n "${EXPECT_IMAGE_SUBSTR}" ]]; then
  image=$(python - <<PY
import json
payload=json.loads("""${taskdef}""")
container=payload.get("taskDefinition", {}).get("containerDefinitions", [{}])[0]
print(container.get("image", ""))
PY
)
  if [[ "${image}" != *"${EXPECT_IMAGE_SUBSTR}"* ]]; then
    echo "WARNING: image does not match expected substring: ${EXPECT_IMAGE_SUBSTR}" >&2
  fi
fi
