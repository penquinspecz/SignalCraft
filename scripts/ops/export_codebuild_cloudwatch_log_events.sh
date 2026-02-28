#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/export_codebuild_cloudwatch_log_events.sh \
    --log-group-name <group> \
    --log-stream-name <stream> \
    --output <path> \
    [--region us-east-1] \
    [--expected-account-id 048622080012] \
    [--start-from-head true|false]

Behavior:
- Calls aws logs get-log-events
- Redacts CloudWatch pagination tokens (nextForwardToken/nextBackwardToken/next*Token)
- Writes deterministic JSON to --output
EOF
}

LOG_GROUP_NAME=""
LOG_STREAM_NAME=""
OUT_PATH=""
REGION="${AWS_REGION:-us-east-1}"
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
START_FROM_HEAD="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --log-group-name)
      LOG_GROUP_NAME="${2:-}"
      shift 2
      ;;
    --log-stream-name)
      LOG_STREAM_NAME="${2:-}"
      shift 2
      ;;
    --output)
      OUT_PATH="${2:-}"
      shift 2
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --expected-account-id)
      EXPECTED_ACCOUNT_ID="${2:-}"
      shift 2
      ;;
    --start-from-head)
      START_FROM_HEAD="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -n "${LOG_GROUP_NAME}" ]] || fail "--log-group-name is required"
[[ -n "${LOG_STREAM_NAME}" ]] || fail "--log-stream-name is required"
[[ -n "${OUT_PATH}" ]] || fail "--output is required"

command -v aws >/dev/null 2>&1 || fail "aws is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

export AWS_REGION="${REGION}"
export AWS_DEFAULT_REGION="${REGION}"
export AWS_PAGER=""

actual_account="$(aws sts get-caller-identity --query Account --output text)"
[[ "${actual_account}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${actual_account}"

tmp_raw="$(mktemp)"
trap 'rm -f "${tmp_raw}"' EXIT

aws logs get-log-events \
  --region "${REGION}" \
  --log-group-name "${LOG_GROUP_NAME}" \
  --log-stream-name "${LOG_STREAM_NAME}" \
  --start-from-head "${START_FROM_HEAD}" \
  --output json > "${tmp_raw}"

mkdir -p "$(dirname "${OUT_PATH}")"
python3 scripts/ops/redact_cloudwatch_tokens.py --input "${tmp_raw}" --output "${OUT_PATH}"

echo "wrote sanitized CloudWatch log events: ${OUT_PATH}"
