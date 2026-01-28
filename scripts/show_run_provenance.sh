#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
  echo "This script uses env vars only; no positional args are accepted." >&2
  echo "Example: BUCKET=jobintel-prod1 PREFIX=jobintel RUN_ID=<run_id> ./scripts/show_run_provenance.sh" >&2
  exit 2
fi

BUCKET="${BUCKET:-${JOBINTEL_S3_BUCKET:-}}"
PREFIX="${PREFIX:-${JOBINTEL_S3_PREFIX:-jobintel}}"
RUN_ID="${RUN_ID:-}"
REGION="${REGION:-${AWS_REGION:-us-east-1}}"

STATUS=0
fail() {
  local msg="$1"
  echo "FAIL: ${msg}" >&2
  STATUS=1
}
finish() {
  if [[ "${STATUS}" -eq 0 ]]; then
    echo "Summary: SUCCESS"
  else
    echo "Summary: FAIL"
  fi
  exit "${STATUS}"
}

command -v aws >/dev/null 2>&1 || fail "aws CLI is required."
command -v jq >/dev/null 2>&1 || fail "jq is required for JSON parsing. Install via: brew install jq"

if [[ -z "${BUCKET}" ]]; then
  fail "BUCKET is required (or set JOBINTEL_S3_BUCKET)."
fi

if [[ "${STATUS}" -ne 0 ]]; then
  finish
fi

if [[ -z "${RUN_ID}" ]]; then
  pointer_key="${PREFIX}/state/last_success.json"
  if [[ -n "${PROVIDER:-}" && -n "${PROFILE:-}" ]]; then
    pointer_key="${PREFIX}/state/${PROVIDER}/${PROFILE}/last_success.json"
  fi
  pointer_uri="s3://${BUCKET}/${pointer_key}"
  pointer_json=$(aws s3 cp "${pointer_uri}" - --region "${REGION}" 2>/dev/null || true)
  if [[ -z "${pointer_json}" ]]; then
    fail "Missing ${pointer_uri}. Set RUN_ID or write pointer first."
    finish
  fi
  RUN_ID=$(printf '%s' "${pointer_json}" | jq -r '.run_id // empty')
  if [[ -z "${RUN_ID}" ]]; then
    fail "Pointer at ${pointer_uri} missing run_id."
    finish
  fi
fi

run_report_uri="s3://${BUCKET}/${PREFIX}/runs/${RUN_ID}/run_report.json"
report=$(aws s3 cp "${run_report_uri}" - --region "${REGION}" 2>/dev/null || true)
if [[ -z "${report}" ]]; then
  fail "Missing run_report at ${run_report_uri}."
  finish
fi

if ! printf '%s' "${report}" | jq -e '.provenance.build' >/dev/null; then
  fail "run_report missing provenance.build (run_id=${RUN_ID}) at ${run_report_uri}. Run a new ECS job to populate build provenance."
  finish
fi

echo "run_report_uri: ${run_report_uri}"
printf '%s' "${report}" | jq -c '.provenance.build'

finish
