#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
  echo "This script uses env vars only; no positional args are accepted." >&2
  echo "Example: BUCKET=jobintel-prod1 PREFIX=jobintel RUN_ID=<run_id> ./scripts/verify_publish_s3.sh" >&2
  exit 2
fi

BUCKET="${BUCKET:-${JOBINTEL_S3_BUCKET:-}}"
PREFIX="${PREFIX:-${JOBINTEL_S3_PREFIX:-jobintel}}"
RUN_ID="${RUN_ID:-}"
REGION="${REGION:-${AWS_REGION:-us-east-1}}"
PROVIDER="${PROVIDER:-openai}"
PROFILE="${PROFILE:-cs}"

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
command -v shasum >/dev/null 2>&1 || fail "shasum is required for sha256 hashing."

if [[ -z "${BUCKET}" || -z "${PREFIX}" ]]; then
  fail "BUCKET and PREFIX are required."
fi

if [[ "${STATUS}" -ne 0 ]]; then
  finish
fi

prefix_clean="${PREFIX%/}"

if [[ -z "${RUN_ID}" ]]; then
  pointer_uri="s3://${BUCKET}/${prefix_clean}/state/last_success.json"
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

run_report_key="${prefix_clean}/runs/${RUN_ID}/run_report.json"
ranked_prefix="${prefix_clean}/runs/${RUN_ID}/${PROVIDER}/${PROFILE}/"
latest_prefix="${prefix_clean}/latest/${PROVIDER}/${PROFILE}/"

head_object() {
  local key="$1"
  aws s3api head-object --bucket "${BUCKET}" --key "${key}" --region "${REGION}" --query ContentType --output text 2>/dev/null
}

list_keys() {
  local key_prefix="$1"
  aws s3api list-objects-v2 \
    --bucket "${BUCKET}" \
    --prefix "${key_prefix}" \
    --region "${REGION}" \
    --query "Contents[].Key" \
    --output json 2>/dev/null || true
}

require_object() {
  local key="$1"
  if ! head_object "${key}" >/dev/null; then
    fail "Missing s3://${BUCKET}/${key}"
    return 1
  fi
  return 0
}

ranked_key=""
latest_has_artifacts="no"

if ! require_object "${run_report_key}"; then
  finish
fi

ranked_keys_json=$(list_keys "${ranked_prefix}")
ranked_key=$(printf '%s' "${ranked_keys_json}" | jq -r '.[]? | select(test("ranked_(jobs|families).*\\.(json|csv)$"))' | head -n 1)
if [[ -z "${ranked_key}" ]]; then
  fail "Missing ranked artifacts under s3://${BUCKET}/${ranked_prefix}"
fi

if head_object "${latest_prefix}run_report.json" >/dev/null; then
  latest_has_artifacts="yes"
else
  latest_keys_json=$(list_keys "${latest_prefix}")
  latest_key=$(printf '%s' "${latest_keys_json}" | jq -r '.[]?' | head -n 1)
  if [[ -n "${latest_key}" ]]; then
    latest_has_artifacts="yes"
  else
    fail "Missing latest artifacts under s3://${BUCKET}/${latest_prefix}"
  fi
fi

tmp_dir=$(mktemp -d)
trap 'rm -rf "${tmp_dir}"' EXIT

download_and_print() {
  local key="$1"
  local label="$2"
  local out_path="${tmp_dir}/$(basename "${key}")"
  aws s3 cp "s3://${BUCKET}/${key}" "${out_path}" --region "${REGION}" >/dev/null 2>&1 || {
    fail "Failed to download s3://${BUCKET}/${key}"
    return
  }
  local ctype
  ctype=$(head_object "${key}" || echo "unknown")
  local sha
  sha=$(shasum -a 256 "${out_path}" | awk '{print $1}')
  echo "${label}: key=${key} content_type=${ctype} sha256=${sha}"
}

download_and_print "${run_report_key}" "run_report"
if [[ -n "${ranked_key}" ]]; then
  download_and_print "${ranked_key}" "ranked_artifact"
fi

run_report_ct=$(head_object "${run_report_key}" || echo "unknown")
if [[ "${run_report_ct}" != "application/json" ]]; then
  fail "run_report.json content-type mismatch: ${run_report_ct}"
fi
if [[ -n "${ranked_key}" ]]; then
  ranked_ct=$(head_object "${ranked_key}" || echo "unknown")
  if [[ "${ranked_ct}" != "application/json" ]]; then
    fail "ranked artifact content-type mismatch: ${ranked_ct}"
  fi
fi

finish
