#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/dr_trigger.sh [--state-machine-arn <arn>] [--region us-east-1] [--expected-account-id 048622080012] [--name <execution-name>]

Manually start a DR orchestrator Step Functions execution with force_run=true.
Requires env: PUBLISH_BUCKET, BACKUP_URI, RECEIPT_BUCKET, NOTIFICATION_TOPIC_ARN, DR_VPC_ID, DR_SUBNET_ID

Example:
  export PUBLISH_BUCKET=jobintel-prod1
  export BACKUP_URI=s3://jobintel-prod1/jobintel/backups/backup-20260221T061624Z
  export RECEIPT_BUCKET=jobintel-prod1
  export NOTIFICATION_TOPIC_ARN=arn:aws:sns:us-east-1:048622080012:signalcraft-dr-notifications
  export DR_VPC_ID=vpc-4362fc3e
  export DR_SUBNET_ID=subnet-11001d5c
  scripts/ops/dr_trigger.sh
EOF
}

STATE_MACHINE_ARN="${STATE_MACHINE_ARN:-arn:aws:states:us-east-1:048622080012:stateMachine:signalcraft-dr-orchestrator-state-machine}"
REGION="${REGION:-us-east-1}"
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
EXEC_NAME="${EXEC_NAME:-$(date -u +%Y%m%dT%H%M%SZ)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state-machine-arn) STATE_MACHINE_ARN="${2:-}"; shift 2 ;;
    --region) REGION="${2:-}"; shift 2 ;;
    --expected-account-id) EXPECTED_ACCOUNT_ID="${2:-}"; shift 2 ;;
    --name) EXEC_NAME="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

command -v aws >/dev/null 2>&1 || fail "aws is required"
command -v jq >/dev/null 2>&1 || fail "jq is required"

: "${PUBLISH_BUCKET:?PUBLISH_BUCKET required}"
: "${BACKUP_URI:?BACKUP_URI required}"
: "${RECEIPT_BUCKET:?RECEIPT_BUCKET required}"
: "${NOTIFICATION_TOPIC_ARN:?NOTIFICATION_TOPIC_ARN required}"
: "${DR_VPC_ID:?DR_VPC_ID required}"
: "${DR_SUBNET_ID:?DR_SUBNET_ID required}"

BACKUP_BUCKET="${BACKUP_BUCKET:-$PUBLISH_BUCKET}"
PREFIX="${PREFIX:-jobintel}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
[[ -n "${REGION}" ]] || REGION="${AWS_REGION}"
export AWS_REGION="${REGION}"
export AWS_DEFAULT_REGION="${REGION}"
export AWS_PAGER=""

ACTUAL=$(aws sts get-caller-identity --query Account --output text)
[[ "${ACTUAL}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${ACTUAL}"

INPUT=$(jq -n \
  --arg expected_account_id "$EXPECTED_ACCOUNT_ID" \
  --arg region "$REGION" \
  --arg publish_bucket "$PUBLISH_BUCKET" \
  --arg publish_prefix "$PREFIX" \
  --arg backup_bucket "$BACKUP_BUCKET" \
  --arg backup_uri "$BACKUP_URI" \
  --arg receipt_bucket "$RECEIPT_BUCKET" \
  --arg receipt_prefix "${PREFIX}/dr-orchestrator/receipts" \
  --arg notification_topic_arn "$NOTIFICATION_TOPIC_ARN" \
  --arg dr_vpc_id "$DR_VPC_ID" \
  --arg dr_subnet_id "$DR_SUBNET_ID" \
  '{
    expected_account_id: $expected_account_id,
    region: $region,
    project: "signalcraft",
    publish_bucket: $publish_bucket,
    publish_prefix: $publish_prefix,
    backup_bucket: $backup_bucket,
    backup_uri: $backup_uri,
    backup_required_keys: ["metadata.json", "state.tar.zst", "manifests.tar.zst"],
    receipt_bucket: $receipt_bucket,
    receipt_prefix: $receipt_prefix,
    notification_topic_arn: $notification_topic_arn,
    provider: "openai",
    profile: "cs",
    expected_marker_file: "openai_top.cs.md",
    max_freshness_hours: 6,
    metric_namespace: "SignalCraft/DR",
    dr_runner_name: "jobintel-dr-runner",
    dr_vpc_id: $dr_vpc_id,
    dr_subnet_id: $dr_subnet_id,
    dr_allowed_cidr: "10.0.0.0/8",
    dr_key_name: "",
    dr_instance_type: "t4g.small",
    dr_ami_id: "",
    namespace: "jobintel",
    validate_timeout_seconds: 300,
    force_run: true
  }')

aws stepfunctions start-execution \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --name "$EXEC_NAME" \
  --input "$INPUT" \
  --region "$REGION" \
  --output json | jq -r '.executionArn'
