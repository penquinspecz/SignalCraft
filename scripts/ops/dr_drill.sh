#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/dr_drill.sh [--backup-uri s3://<bucket>/<prefix>/backups/<backup_id>] \
    [--image-ref <repo>@sha256:<digest>|<repo>:<tag>] \
    [--auto-promote true|false] \
    [--teardown true|false] \
    [--allow-promote-bypass true|false] \
    [--start-at bringup|restore|validate|promote|teardown] \
    [--stop-after bringup|restore|validate|promote] \
    [--max-attempts <N>] \
    [--no-retry] \
    [--diagnostics-only] \
    [--validate-only] \
    [--skip-workload-assume] \
    [--allow-full-drill] \
    [--allow-tag] \
    [--receipt-dir /path/to/prior-receipt] \
    [--kubeconfig /path/to/k3s.public.yaml]

Defaults:
  --auto-promote false
  --teardown true
  --allow-promote-bypass false
  --start-at bringup
  --stop-after promote
  --allow-full-drill false

Notes:
  - Primary operator workflow (cost discipline): bringup-only once -> restore-only once -> validate-only iterations -> final teardown.
  - Promote executes only when --auto-promote=true and --allow-promote-bypass=true.
  - Teardown runs at the end when --teardown=true, even if earlier phases fail.
  - Full drill safety: start-at=bringup with no stop-after and teardown=true requires --allow-full-drill or ALLOW_FULL_DRILL=1.
  - --diagnostics-only runs bringup + cluster introspection + teardown.
  - --validate-only runs validate only (use --kubeconfig, and typically --teardown false).
  - --skip-workload-assume enables validate iteration mode (skip cronjob baseline assumption; require control-plane ConfigMaps + ECR pull secret + successful validate job).
  - --receipt-dir auto-loads kubeconfig for restore/validate starts when --kubeconfig is omitted.
  - Required env for bringup/teardown: TF_VAR_vpc_id, TF_VAR_subnet_id.
  - When mutation phases run and TF_BACKEND_MODE=remote (default), set TF_BACKEND_BUCKET, TF_BACKEND_KEY, TF_BACKEND_DYNAMODB_TABLE.
  - IMAGE_REF must be digest-pinned (repo@sha256:<digest>) for non-dev; use --allow-tag for tag in dev iteration only.
EOF
}

parse_bool() {
  local raw="${1:-}"
  case "${raw,,}" in
    1|true|yes|y) echo "true" ;;
    0|false|no|n) echo "false" ;;
    *) return 1 ;;
  esac
}

normalize_phase() {
  local raw="${1:-}"
  case "${raw,,}" in
    bringup|restore|validate|promote|teardown) echo "${raw,,}" ;;
    *) return 1 ;;
  esac
}

phase_index() {
  case "${1:-}" in
    bringup) echo 1 ;;
    restore) echo 2 ;;
    validate) echo 3 ;;
    promote) echo 4 ;;
    teardown) echo 5 ;;
    *) return 1 ;;
  esac
}

phase_enabled_in_window() {
  local phase="$1"
  local start="$2"
  local stop="$3"
  local start_i stop_i phase_i
  start_i="$(phase_index "${start}")"
  stop_i="$(phase_index "${stop}")"
  phase_i="$(phase_index "${phase}")"
  (( phase_i >= start_i && phase_i <= stop_i ))
}

mark_stop_reason() {
  local reason="$1"
  STOP_REASON="${reason}"
  printf '%s\n' "${reason}" > "${RECEIPT_DIR}/drill.stop_reason.txt"
}

BACKUP_URI=""
IMAGE_REF=""
AUTO_PROMOTE_RAW="false"
TEARDOWN_RAW="true"
ALLOW_PROMOTE_BYPASS_RAW="false"
START_AT_RAW="bringup"
STOP_AFTER_RAW="promote"
STOP_AFTER_EXPLICIT=0
MAX_PHASE_ATTEMPTS_RAW="${DR_MAX_PHASE_ATTEMPTS:-3}"
DR_VALIDATE_MAX_RETRIES_RAW="${DR_VALIDATE_MAX_RETRIES:-2}"
DR_VALIDATE_RETRY_BACKOFF_SECONDS_RAW="${DR_VALIDATE_RETRY_BACKOFF_SECONDS:-15}"
NO_RETRY="false"
DIAGNOSTICS_ONLY="false"
VALIDATE_ONLY="false"
VALIDATE_SKIP_WORKLOAD_ASSUME="false"
ALLOW_FULL_DRILL_FLAG="false"
INPUT_RECEIPT_DIR=""
KUBECONFIG_INPUT=""
ALLOW_TAG="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-uri)
      BACKUP_URI="${2:-}"
      shift 2
      ;;
    --image-ref)
      IMAGE_REF="${2:-}"
      shift 2
      ;;
    --auto-promote)
      AUTO_PROMOTE_RAW="${2:-}"
      shift 2
      ;;
    --teardown)
      TEARDOWN_RAW="${2:-}"
      shift 2
      ;;
    --allow-promote-bypass)
      ALLOW_PROMOTE_BYPASS_RAW="${2:-}"
      shift 2
      ;;
    --start-at)
      START_AT_RAW="${2:-}"
      shift 2
      ;;
    --stop-after)
      STOP_AFTER_RAW="${2:-}"
      STOP_AFTER_EXPLICIT=1
      shift 2
      ;;
    --max-attempts)
      MAX_PHASE_ATTEMPTS_RAW="${2:-}"
      shift 2
      ;;
    --no-retry)
      NO_RETRY="true"
      shift
      ;;
    --diagnostics-only)
      DIAGNOSTICS_ONLY="true"
      shift
      ;;
    --validate-only)
      VALIDATE_ONLY="true"
      shift
      ;;
    --skip-workload-assume)
      VALIDATE_SKIP_WORKLOAD_ASSUME="true"
      shift
      ;;
    --allow-full-drill)
      ALLOW_FULL_DRILL_FLAG="true"
      shift
      ;;
    --receipt-dir)
      INPUT_RECEIPT_DIR="${2:-}"
      shift 2
      ;;
    --kubeconfig)
      KUBECONFIG_INPUT="${2:-}"
      shift 2
      ;;
    --allow-tag)
      ALLOW_TAG="true"
      shift
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

AUTO_PROMOTE="$(parse_bool "${AUTO_PROMOTE_RAW}")" || fail "Invalid --auto-promote: ${AUTO_PROMOTE_RAW}"
TEARDOWN="$(parse_bool "${TEARDOWN_RAW}")" || fail "Invalid --teardown: ${TEARDOWN_RAW}"
ALLOW_PROMOTE_BYPASS="$(parse_bool "${ALLOW_PROMOTE_BYPASS_RAW}")" || fail "Invalid --allow-promote-bypass: ${ALLOW_PROMOTE_BYPASS_RAW}"
START_AT="$(normalize_phase "${START_AT_RAW}")" || fail "Invalid --start-at: ${START_AT_RAW}"
STOP_AFTER="$(normalize_phase "${STOP_AFTER_RAW}")" || fail "Invalid --stop-after: ${STOP_AFTER_RAW}"
[[ "${STOP_AFTER}" != "teardown" ]] || fail "--stop-after cannot be teardown"

if [[ "${DIAGNOSTICS_ONLY}" == "true" && "${VALIDATE_ONLY}" == "true" ]]; then
  fail "--diagnostics-only and --validate-only are mutually exclusive"
fi
if [[ "${DIAGNOSTICS_ONLY}" == "true" ]]; then
  START_AT="bringup"
  STOP_AFTER="bringup"
fi
if [[ "${VALIDATE_ONLY}" == "true" ]]; then
  START_AT="validate"
  STOP_AFTER="validate"
fi

ALLOW_FULL_DRILL_ENV_RAW="${ALLOW_FULL_DRILL:-0}"
ALLOW_FULL_DRILL_ENV="$(parse_bool "${ALLOW_FULL_DRILL_ENV_RAW}")" || fail "Invalid ALLOW_FULL_DRILL: ${ALLOW_FULL_DRILL_ENV_RAW}"
ALLOW_FULL_DRILL="false"
if [[ "${ALLOW_FULL_DRILL_FLAG}" == "true" || "${ALLOW_FULL_DRILL_ENV}" == "true" ]]; then
  ALLOW_FULL_DRILL="true"
fi
FULL_DRILL_REQUESTED="false"
if [[ "${START_AT}" == "bringup" && "${TEARDOWN}" == "true" && "${STOP_AFTER_EXPLICIT}" -eq 0 && "${DIAGNOSTICS_ONLY}" != "true" && "${VALIDATE_ONLY}" != "true" ]]; then
  FULL_DRILL_REQUESTED="true"
fi
if [[ "${FULL_DRILL_REQUESTED}" == "true" && "${ALLOW_FULL_DRILL}" != "true" ]]; then
  fail "Full drill requires explicit allow flag; use validate-only/stop-after."
fi

# M19A: When IMAGE_REF is provided, require digest pinning unless --allow-tag
if [[ -n "${IMAGE_REF}" ]]; then
  allow_tag_arg=()
  [[ "${ALLOW_TAG}" == "true" ]] && allow_tag_arg=(--allow-tag)
  python3 "${ROOT_DIR}/scripts/ops/assert_image_ref_digest.py" "${IMAGE_REF}" --context "dr_drill" "${allow_tag_arg[@]:-}" \
    || fail "IMAGE_REF must be digest-pinned; use --allow-tag for dev iteration only"
fi

if [[ "${START_AT}" != "teardown" ]]; then
  local_start_i="$(phase_index "${START_AT}")"
  local_stop_i="$(phase_index "${STOP_AFTER}")"
  (( local_start_i <= local_stop_i )) || fail "--start-at (${START_AT}) must be <= --stop-after (${STOP_AFTER})"
fi

MAX_PHASE_ATTEMPTS="${MAX_PHASE_ATTEMPTS_RAW}"
[[ "${MAX_PHASE_ATTEMPTS}" =~ ^[0-9]+$ ]] || fail "--max-attempts/DR_MAX_PHASE_ATTEMPTS must be an integer"
(( MAX_PHASE_ATTEMPTS >= 1 )) || fail "--max-attempts/DR_MAX_PHASE_ATTEMPTS must be >= 1"
DR_VALIDATE_MAX_RETRIES="${DR_VALIDATE_MAX_RETRIES_RAW}"
[[ "${DR_VALIDATE_MAX_RETRIES}" =~ ^[0-9]+$ ]] || fail "DR_VALIDATE_MAX_RETRIES must be an integer"
DR_VALIDATE_RETRY_BACKOFF_SECONDS="${DR_VALIDATE_RETRY_BACKOFF_SECONDS_RAW}"
[[ "${DR_VALIDATE_RETRY_BACKOFF_SECONDS}" =~ ^[0-9]+$ ]] || fail "DR_VALIDATE_RETRY_BACKOFF_SECONDS must be an integer"
if [[ "${NO_RETRY}" == "true" ]]; then
  MAX_PHASE_ATTEMPTS=1
  DR_VALIDATE_MAX_RETRIES=0
fi

for bin in aws terraform kubectl python3 rg curl git; do
  command -v "${bin}" >/dev/null 2>&1 || fail "Missing required command: ${bin}"
done

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
NAMESPACE="${NAMESPACE:-jobintel}"
TF_BACKEND_MODE="${TF_BACKEND_MODE:-remote}"

export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER
export TF_IN_AUTOMATION=1
export TF_INPUT=0
export TF_BACKEND_MODE

RUN_BRINGUP=0
RUN_RESTORE=0
RUN_VALIDATE=0
RUN_PROMOTE=0
RUN_DIAGNOSTICS=0

if [[ "${START_AT}" != "teardown" ]]; then
  phase_enabled_in_window "bringup" "${START_AT}" "${STOP_AFTER}" && RUN_BRINGUP=1
  phase_enabled_in_window "restore" "${START_AT}" "${STOP_AFTER}" && RUN_RESTORE=1
  phase_enabled_in_window "validate" "${START_AT}" "${STOP_AFTER}" && RUN_VALIDATE=1
  phase_enabled_in_window "promote" "${START_AT}" "${STOP_AFTER}" && RUN_PROMOTE=1
fi
if [[ "${DIAGNOSTICS_ONLY}" == "true" ]]; then
  RUN_DIAGNOSTICS=1
fi

KUBECONFIG_SELECTION_SOURCE="unset"
KUBECONFIG_SELECTION_RECEIPT_DIR=""
if [[ -n "${KUBECONFIG_INPUT}" ]]; then
  KUBECONFIG_SELECTION_SOURCE="arg_kubeconfig"
fi
if [[ -z "${KUBECONFIG_INPUT}" && -n "${INPUT_RECEIPT_DIR}" && "${RUN_BRINGUP}" -eq 0 && ( "${RUN_RESTORE}" -eq 1 || "${RUN_VALIDATE}" -eq 1 ) ]]; then
  [[ -d "${INPUT_RECEIPT_DIR}" ]] || fail "Provided --receipt-dir not found: ${INPUT_RECEIPT_DIR}"
  resolved_kubeconfig=""
  if [[ -s "${INPUT_RECEIPT_DIR}/kubeconfig.path.txt" ]]; then
    candidate="$(tr -d '[:space:]' < "${INPUT_RECEIPT_DIR}/kubeconfig.path.txt" || true)"
    if [[ -n "${candidate}" && -s "${candidate}" ]]; then
      resolved_kubeconfig="${candidate}"
    fi
  fi
  for candidate in \
    "${INPUT_RECEIPT_DIR}/kubeconfig.yaml" \
    "${INPUT_RECEIPT_DIR}/k3s.public.yaml" \
    "${INPUT_RECEIPT_DIR}/k3s.public.input.yaml"; do
    if [[ -z "${resolved_kubeconfig}" && -s "${candidate}" ]]; then
      resolved_kubeconfig="${candidate}"
    fi
  done
  [[ -n "${resolved_kubeconfig}" ]] || fail "Unable to resolve kubeconfig from --receipt-dir=${INPUT_RECEIPT_DIR}"
  KUBECONFIG_INPUT="${resolved_kubeconfig}"
  KUBECONFIG_SELECTION_SOURCE="receipt_dir_autoload"
  KUBECONFIG_SELECTION_RECEIPT_DIR="${INPUT_RECEIPT_DIR}"
fi

REQUIRES_TERRAFORM_MUTATION=0
if [[ "${RUN_BRINGUP}" -eq 1 || "${TEARDOWN}" == "true" ]]; then
  REQUIRES_TERRAFORM_MUTATION=1
fi
if [[ "${REQUIRES_TERRAFORM_MUTATION}" -eq 1 ]]; then
  [[ -n "${TF_VAR_vpc_id:-}" ]] || fail "TF_VAR_vpc_id is required for bringup/teardown"
  [[ -n "${TF_VAR_subnet_id:-}" ]] || fail "TF_VAR_subnet_id is required for bringup/teardown"
  if [[ "${TF_BACKEND_MODE}" == "remote" ]]; then
    [[ -n "${TF_BACKEND_BUCKET:-}" ]] || fail "TF_BACKEND_BUCKET is required when TF_BACKEND_MODE=remote"
    [[ -n "${TF_BACKEND_KEY:-}" ]] || fail "TF_BACKEND_KEY is required when TF_BACKEND_MODE=remote"
    [[ -n "${TF_BACKEND_DYNAMODB_TABLE:-}" ]] || fail "TF_BACKEND_DYNAMODB_TABLE is required when TF_BACKEND_MODE=remote"
  fi
fi
if [[ "${RUN_RESTORE}" -eq 1 && -z "${BACKUP_URI}" ]]; then
  usage
  fail "--backup-uri is required when restore phase executes"
fi
if [[ "${RUN_VALIDATE}" -eq 1 && "${RUN_BRINGUP}" -eq 0 && -z "${KUBECONFIG_INPUT}" ]]; then
  fail "--kubeconfig is required when starting at validate without bringup (or provide --receipt-dir)"
fi
if [[ "${RUN_RESTORE}" -eq 1 && "${RUN_BRINGUP}" -eq 0 && -z "${KUBECONFIG_INPUT}" ]]; then
  fail "--kubeconfig is required when starting at restore without bringup (or provide --receipt-dir)"
fi

RECEIPT_BASE="${RECEIPT_BASE:-/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles}"
RUN_ID="${RUN_ID:-m19-dr-drill-$(date -u +%Y%m%dT%H%M%SZ)}"
RECEIPT_DIR="${RECEIPT_BASE}/${RUN_ID}"
mkdir -p "${RECEIPT_DIR}" || fail "Unable to create receipt dir: ${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" || fail "Receipt dir is not writable: ${RECEIPT_DIR}"

START_TS="$(ts)"
GIT_SHA="$(git -C "${ROOT_DIR}" rev-parse HEAD)"
ACTUAL_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
[[ "${ACTUAL_ACCOUNT_ID}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${ACTUAL_ACCOUNT_ID}"
MY_IP="$(curl -fsSL https://checkip.amazonaws.com | tr -d '[:space:]' || true)"

COST_INSTANCE_TYPE_INPUT="${TF_VAR_instance_type:-${DR_ESTIMATED_INSTANCE_TYPE:-t4g.medium}}"
COST_EBS_ROOT_GB_INPUT="${DR_EBS_ROOT_GB_ESTIMATE:-8}"
if [[ -n "${DR_ESTIMATED_RUNTIME_MINUTES:-}" ]]; then
  COST_ESTIMATED_RUNTIME_MINUTES="${DR_ESTIMATED_RUNTIME_MINUTES}"
else
  COST_ESTIMATED_RUNTIME_MINUTES=0
  [[ "${RUN_BRINGUP}" -eq 1 ]] && COST_ESTIMATED_RUNTIME_MINUTES=$((COST_ESTIMATED_RUNTIME_MINUTES + 12))
  [[ "${RUN_RESTORE}" -eq 1 ]] && COST_ESTIMATED_RUNTIME_MINUTES=$((COST_ESTIMATED_RUNTIME_MINUTES + 10))
  [[ "${RUN_VALIDATE}" -eq 1 ]] && COST_ESTIMATED_RUNTIME_MINUTES=$((COST_ESTIMATED_RUNTIME_MINUTES + 12))
  [[ "${RUN_DIAGNOSTICS}" -eq 1 ]] && COST_ESTIMATED_RUNTIME_MINUTES=$((COST_ESTIMATED_RUNTIME_MINUTES + 6))
  if [[ "${RUN_PROMOTE}" -eq 1 && "${AUTO_PROMOTE}" == "true" ]]; then
    COST_ESTIMATED_RUNTIME_MINUTES=$((COST_ESTIMATED_RUNTIME_MINUTES + 2))
  fi
  if [[ "${TEARDOWN}" == "true" ]]; then
    COST_ESTIMATED_RUNTIME_MINUTES=$((COST_ESTIMATED_RUNTIME_MINUTES + 8))
  fi
fi
[[ "${COST_ESTIMATED_RUNTIME_MINUTES}" =~ ^[0-9]+$ ]] || fail "Estimated runtime minutes must be an integer"
[[ "${COST_EBS_ROOT_GB_INPUT}" =~ ^[0-9]+$ ]] || fail "DR_EBS_ROOT_GB_ESTIMATE must be an integer"

python3 - "${RECEIPT_DIR}/drill.cost.inputs.json" "${COST_INSTANCE_TYPE_INPUT}" "${COST_ESTIMATED_RUNTIME_MINUTES}" "${COST_EBS_ROOT_GB_INPUT}" "${START_TS}" "${FULL_DRILL_REQUESTED}" "${ALLOW_FULL_DRILL}" <<'PY'
import json
import pathlib
import sys

out, instance_type, runtime_minutes, ebs_gb, ts_utc, full_mode, allowed = sys.argv[1:]
payload = {
    "schema_version": 1,
    "recorded_at_utc": ts_utc,
    "instance_type_input": instance_type,
    "estimated_runtime_minutes": int(runtime_minutes),
    "ebs_root_gb_input": int(ebs_gb),
    "full_drill_requested": full_mode == "true",
    "full_drill_allowed": allowed == "true",
}
pathlib.Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

  python3 - "${BACKUP_URI}" "${RECEIPT_DIR}" "${START_TS}" "${GIT_SHA}" "${IMAGE_REF}" "${ACTUAL_ACCOUNT_ID}" "${AWS_REGION}" "${AUTO_PROMOTE}" "${TEARDOWN}" "${ALLOW_PROMOTE_BYPASS}" "${NAMESPACE}" "${MY_IP}" "${TF_BACKEND_MODE}" "${TF_VAR_vpc_id:-}" "${TF_VAR_subnet_id:-}" "${TF_VAR_allowed_cidr:-}" "${START_AT}" "${STOP_AFTER}" "${MAX_PHASE_ATTEMPTS}" "${DR_VALIDATE_MAX_RETRIES}" "${DIAGNOSTICS_ONLY}" "${VALIDATE_ONLY}" "${RUN_BRINGUP}" "${RUN_RESTORE}" "${RUN_VALIDATE}" "${RUN_PROMOTE}" "${RUN_DIAGNOSTICS}" "${KUBECONFIG_INPUT}" "${NO_RETRY}" "${ALLOW_FULL_DRILL}" "${FULL_DRILL_REQUESTED}" "${STOP_AFTER_EXPLICIT}" "${COST_INSTANCE_TYPE_INPUT}" "${COST_ESTIMATED_RUNTIME_MINUTES}" "${COST_EBS_ROOT_GB_INPUT}" "${INPUT_RECEIPT_DIR}" "${KUBECONFIG_SELECTION_SOURCE}" "${KUBECONFIG_SELECTION_RECEIPT_DIR}" "${VALIDATE_SKIP_WORKLOAD_ASSUME}" <<'PY'
import json
import pathlib
import sys

(
    backup_uri,
    receipt_dir,
    start_ts,
    git_sha,
    image_ref,
    account_id,
    region,
    auto_promote,
    teardown,
    bypass,
    namespace,
    my_ip,
    backend_mode,
    vpc_id,
    subnet_id,
    allowed_cidr,
    start_at,
    stop_after,
    max_attempts,
    validate_retries,
    diagnostics_only,
    validate_only,
    run_bringup,
    run_restore,
    run_validate,
    run_promote,
    run_diagnostics,
    kubeconfig_input,
    no_retry,
    allow_full_drill,
    full_drill_requested,
    stop_after_explicit,
    cost_instance_type,
    cost_estimated_minutes,
    cost_ebs_root_gb,
    input_receipt_dir,
    kubeconfig_selection_source,
    kubeconfig_selection_receipt_dir,
    validate_skip_workload_assume,
) = sys.argv[1:]
payload = {
    "schema_version": 1,
    "run_id": pathlib.Path(receipt_dir).name,
    "start_timestamp_utc": start_ts,
    "git_sha": git_sha,
    "backup_uri": backup_uri,
    "image_ref": image_ref,
    "aws_account_id": account_id,
    "aws_region": region,
    "auto_promote": auto_promote == "true",
    "teardown": teardown == "true",
    "allow_promote_bypass": bypass == "true",
    "namespace": namespace,
    "operator_public_ip": my_ip,
    "terraform_backend_mode": backend_mode,
    "terraform_vpc_id": vpc_id,
    "terraform_subnet_id": subnet_id,
    "terraform_allowed_cidr": allowed_cidr,
    "start_at": start_at,
    "stop_after": stop_after,
    "max_attempts": int(max_attempts),
    "validate_max_retries": int(validate_retries),
    "diagnostics_only": diagnostics_only == "true",
    "validate_only": validate_only == "true",
    "no_retry": no_retry == "true",
    "allow_full_drill": allow_full_drill == "true",
    "full_drill_requested": full_drill_requested == "true",
    "stop_after_explicit": stop_after_explicit == "1",
    "cost_instance_type_input": cost_instance_type,
    "cost_estimated_runtime_minutes": int(cost_estimated_minutes),
    "cost_ebs_root_gb_input": int(cost_ebs_root_gb),
    "run_bringup": run_bringup == "1",
    "run_restore": run_restore == "1",
    "run_validate": run_validate == "1",
    "run_promote": run_promote == "1",
    "run_diagnostics": run_diagnostics == "1",
    "input_kubeconfig": kubeconfig_input,
    "input_receipt_dir": input_receipt_dir,
    "kubeconfig_selection_source": kubeconfig_selection_source,
    "kubeconfig_selection_receipt_dir": kubeconfig_selection_receipt_dir,
    "validate_skip_workload_assume": validate_skip_workload_assume == "true",
}
pathlib.Path(receipt_dir, "drill.context.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

PHASE_DIR="${RECEIPT_DIR}/phases"
mkdir -p "${PHASE_DIR}"

OVERALL_STATUS="running"
FAILED_PHASE=""
FAILED_ERROR=""
STOP_REASON=""
INSTANCE_ID=""
PUBLIC_IP=""
SECURITY_GROUP_ID=""
KEY_NAME=""
ACTUAL_INSTANCE_TYPE=""
ACTUAL_EBS_ROOT_GB=""
DR_JOB_NAME=""
DR_RUN_ID=""
DR_KUBECONFIG_RAW="${RECEIPT_DIR}/k3s.raw.yaml"
DR_KUBECONFIG_PUBLIC="${RECEIPT_DIR}/k3s.public.yaml"
DR_KUBECONFIG_STANDARD="${RECEIPT_DIR}/kubeconfig.yaml"
KUBE_HOME="${RECEIPT_DIR}/kube-home"
mkdir -p "${KUBE_HOME}"
if [[ -n "${KUBECONFIG_INPUT}" ]]; then
  [[ -s "${KUBECONFIG_INPUT}" ]] || fail "Provided --kubeconfig not found or empty: ${KUBECONFIG_INPUT}"
  DR_KUBECONFIG_PUBLIC="${RECEIPT_DIR}/k3s.public.input.yaml"
  cp "${KUBECONFIG_INPUT}" "${DR_KUBECONFIG_PUBLIC}"
fi

write_kubeconfig_receipts() {
  local source="$1"
  local source_receipt_dir="${2:-}"
  KUBECONFIG_SELECTION_SOURCE="${source}"
  KUBECONFIG_SELECTION_RECEIPT_DIR="${source_receipt_dir}"
  [[ -s "${DR_KUBECONFIG_PUBLIC}" ]] || fail "kubeconfig not found for receipt write: ${DR_KUBECONFIG_PUBLIC}"
  cp "${DR_KUBECONFIG_PUBLIC}" "${DR_KUBECONFIG_STANDARD}"
  DR_KUBECONFIG_PUBLIC="${DR_KUBECONFIG_STANDARD}"
  printf '%s\n' "${DR_KUBECONFIG_PUBLIC}" > "${RECEIPT_DIR}/kubeconfig.path.txt"
  cat > "${RECEIPT_DIR}/kubeconfig.used.env" <<EOF
KUBECONFIG_USED_PATH=${DR_KUBECONFIG_PUBLIC}
KUBECONFIG_SOURCE=${source}
KUBECONFIG_INPUT=${KUBECONFIG_INPUT}
KUBECONFIG_INPUT_RECEIPT_DIR=${source_receipt_dir}
EOF
}

write_phase_receipt() {
  local phase="$1"
  local status="$2"
  local attempts="$3"
  local repaired="$4"
  local command_hint="$5"
  local last_log="$6"
  local last_error="$7"
  local started_at="$8"
  local ended_at="$9"
  PHASE_NAME="${phase}" \
  PHASE_STATUS="${status}" \
  PHASE_ATTEMPTS="${attempts}" \
  PHASE_REPAIRED="${repaired}" \
  PHASE_COMMAND_HINT="${command_hint}" \
  PHASE_LAST_LOG="${last_log}" \
  PHASE_LAST_ERROR="${last_error}" \
  PHASE_STARTED_AT="${started_at}" \
  PHASE_ENDED_AT="${ended_at}" \
  PHASE_PATH="${PHASE_DIR}/${phase}.json" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "phase": os.environ["PHASE_NAME"],
    "status": os.environ["PHASE_STATUS"],
    "attempts": int(os.environ["PHASE_ATTEMPTS"]),
    "repair_applied": os.environ["PHASE_REPAIRED"] == "1",
    "command_hint": os.environ["PHASE_COMMAND_HINT"],
    "last_attempt_log": os.environ["PHASE_LAST_LOG"],
    "last_error_tail": os.environ["PHASE_LAST_ERROR"],
    "started_at_utc": os.environ["PHASE_STARTED_AT"],
    "ended_at_utc": os.environ["PHASE_ENDED_AT"],
}
Path(os.environ["PHASE_PATH"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

write_skipped_phase() {
  local phase="$1"
  local reason="$2"
  write_phase_receipt "${phase}" "skipped" 0 0 "n/a" "" "${reason}" "$(ts)" "$(ts)"
}

finalize_summary() {
  local exit_code="$1"
  local end_ts
  end_ts="$(ts)"
  SUMMARY_EXIT_CODE="${exit_code}" \
  SUMMARY_END_TS="${end_ts}" \
  SUMMARY_OVERALL="${OVERALL_STATUS}" \
  SUMMARY_FAILED_PHASE="${FAILED_PHASE}" \
  SUMMARY_FAILED_ERROR="${FAILED_ERROR}" \
  SUMMARY_INSTANCE_ID="${INSTANCE_ID}" \
  SUMMARY_PUBLIC_IP="${PUBLIC_IP}" \
  SUMMARY_SECURITY_GROUP_ID="${SECURITY_GROUP_ID}" \
  SUMMARY_KEY_NAME="${KEY_NAME}" \
  SUMMARY_ACTUAL_INSTANCE_TYPE="${ACTUAL_INSTANCE_TYPE}" \
  SUMMARY_ACTUAL_EBS_ROOT_GB="${ACTUAL_EBS_ROOT_GB}" \
  SUMMARY_DR_JOB_NAME="${DR_JOB_NAME}" \
  SUMMARY_DR_RUN_ID="${DR_RUN_ID}" \
  SUMMARY_KUBECONFIG_PUBLIC="${DR_KUBECONFIG_PUBLIC}" \
  SUMMARY_STOP_REASON="${STOP_REASON}" \
  SUMMARY_START_AT="${START_AT}" \
  SUMMARY_STOP_AFTER="${STOP_AFTER}" \
  SUMMARY_DIAGNOSTICS_ONLY="${DIAGNOSTICS_ONLY}" \
  SUMMARY_VALIDATE_ONLY="${VALIDATE_ONLY}" \
  SUMMARY_TEARDOWN="${TEARDOWN}" \
  SUMMARY_PHASE_DIR="${PHASE_DIR}" \
  SUMMARY_COST_INPUT_FILE="${RECEIPT_DIR}/drill.cost.inputs.json" \
  SUMMARY_COST_ACTUAL_FILE="${RECEIPT_DIR}/drill.cost.actual.json" \
  SUMMARY_PHASE_TIMESTAMPS_FILE="${RECEIPT_DIR}/drill.phase_timestamps.json" \
  SUMMARY_RECEIPT_DIR="${RECEIPT_DIR}" \
  SUMMARY_START_TS="${START_TS}" \
  SUMMARY_RUN_ID="${RUN_ID}" \
  SUMMARY_FILE="${RECEIPT_DIR}/drill.summary.json" \
  python3 - <<'PY'
import json
import os
from pathlib import Path
from datetime import datetime

phase_dir = Path(os.environ["SUMMARY_PHASE_DIR"])
phases = []
if phase_dir.exists():
    for p in sorted(phase_dir.glob("*.json")):
        try:
            phases.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            phases.append({"phase": p.stem, "status": "corrupt_receipt"})

cost_inputs = {}
cost_inputs_path = Path(os.environ["SUMMARY_COST_INPUT_FILE"])
if cost_inputs_path.exists():
    try:
        cost_inputs = json.loads(cost_inputs_path.read_text(encoding="utf-8"))
    except Exception:
        cost_inputs = {"status": "corrupt"}

cost_actual = {}
cost_actual_path = Path(os.environ["SUMMARY_COST_ACTUAL_FILE"])
if cost_actual_path.exists():
    try:
        cost_actual = json.loads(cost_actual_path.read_text(encoding="utf-8"))
    except Exception:
        cost_actual = {"status": "corrupt"}

phase_timestamps = [
    {
        "phase": p.get("phase", ""),
        "status": p.get("status", ""),
        "started_at_utc": p.get("started_at_utc", ""),
        "ended_at_utc": p.get("ended_at_utc", ""),
    }
    for p in phases
]
Path(os.environ["SUMMARY_PHASE_TIMESTAMPS_FILE"]).write_text(
    json.dumps({"schema_version": 1, "phases": phase_timestamps}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
runtime_seconds = None
try:
    start_dt = datetime.strptime(os.environ["SUMMARY_START_TS"], "%Y-%m-%dT%H:%M:%SZ")
    end_dt = datetime.strptime(os.environ["SUMMARY_END_TS"], "%Y-%m-%dT%H:%M:%SZ")
    runtime_seconds = int((end_dt - start_dt).total_seconds())
except Exception:
    runtime_seconds = None

payload = {
    "schema_version": 1,
    "run_id": os.environ["SUMMARY_RUN_ID"],
    "start_timestamp_utc": os.environ["SUMMARY_START_TS"],
    "end_timestamp_utc": os.environ["SUMMARY_END_TS"],
    "overall_status": os.environ["SUMMARY_OVERALL"],
    "exit_code": int(os.environ["SUMMARY_EXIT_CODE"]),
    "failed_phase": os.environ["SUMMARY_FAILED_PHASE"],
    "failed_error": os.environ["SUMMARY_FAILED_ERROR"],
    "instance_id": os.environ["SUMMARY_INSTANCE_ID"],
    "public_ip": os.environ["SUMMARY_PUBLIC_IP"],
    "security_group_id": os.environ["SUMMARY_SECURITY_GROUP_ID"],
    "key_name": os.environ["SUMMARY_KEY_NAME"],
    "actual_instance_type": os.environ["SUMMARY_ACTUAL_INSTANCE_TYPE"],
    "actual_ebs_root_gb": os.environ["SUMMARY_ACTUAL_EBS_ROOT_GB"],
    "dr_job_name": os.environ["SUMMARY_DR_JOB_NAME"],
    "dr_run_id": os.environ["SUMMARY_DR_RUN_ID"],
    "kubeconfig_public": os.environ["SUMMARY_KUBECONFIG_PUBLIC"],
    "stop_reason": os.environ["SUMMARY_STOP_REASON"],
    "start_at": os.environ["SUMMARY_START_AT"],
    "stop_after": os.environ["SUMMARY_STOP_AFTER"],
    "diagnostics_only": os.environ["SUMMARY_DIAGNOSTICS_ONLY"] == "true",
    "validate_only": os.environ["SUMMARY_VALIDATE_ONLY"] == "true",
    "teardown": os.environ["SUMMARY_TEARDOWN"] == "true",
    "cost_inputs": cost_inputs,
    "cost_actual": cost_actual,
    "runtime_seconds": runtime_seconds,
    "runtime_minutes_rounded_up": (runtime_seconds + 59) // 60 if runtime_seconds is not None else None,
    "phase_timestamps_file": os.environ["SUMMARY_PHASE_TIMESTAMPS_FILE"],
    "receipt_dir": os.environ["SUMMARY_RECEIPT_DIR"],
    "phases": phases,
}
Path(os.environ["SUMMARY_FILE"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

on_exit() {
  local rc="$?"
  set +e
  if [[ "${OVERALL_STATUS}" == "running" ]]; then
    if [[ "${rc}" -eq 0 ]]; then
      OVERALL_STATUS="success"
    else
      OVERALL_STATUS="failed"
    fi
  fi
  if [[ -z "${STOP_REASON}" ]]; then
    if [[ "${rc}" -eq 0 ]]; then
      STOP_REASON="completed requested phases"
    else
      STOP_REASON="execution failed before explicit stop reason"
    fi
  fi
  finalize_summary "${rc}"
  if [[ "${rc}" -eq 0 ]]; then
    note "dr drill complete: receipt_dir=${RECEIPT_DIR}"
  else
    note "dr drill failed: receipt_dir=${RECEIPT_DIR}"
  fi
}
trap on_exit EXIT

wait_for_ssm_online() {
  local instance_id="$1"
  local max_wait_seconds="${2:-300}"
  local slept=0
  while (( slept < max_wait_seconds )); do
    local status
    status="$(aws ssm describe-instance-information \
      --filters "Key=InstanceIds,Values=${instance_id}" \
      --query "InstanceInformationList[0].PingStatus" \
      --output text 2>/dev/null || true)"
    if [[ "${status}" == "Online" ]]; then
      return 0
    fi
    sleep 5
    slept=$((slept + 5))
  done
  return 1
}

fetch_k3s_kubeconfig_from_ssm() {
  local instance_id="$1"
  local invocation_json="${RECEIPT_DIR}/ssm.k3s.get-command-invocation.json"
  local cmd_id
  local ssm_params='{"commands":["set -eu","sudo test -s /etc/rancher/k3s/k3s.yaml","sudo cat /etc/rancher/k3s/k3s.yaml"]}'

  cmd_id="$(aws ssm send-command \
    --instance-ids "${instance_id}" \
    --document-name "AWS-RunShellScript" \
    --parameters "${ssm_params}" \
    --query "Command.CommandId" \
    --output text)"
  [[ -n "${cmd_id}" ]] || fail "SSM send-command did not return CommandId"

  local attempts=0
  while (( attempts < 90 )); do
    attempts=$((attempts + 1))
    if aws ssm get-command-invocation --command-id "${cmd_id}" --instance-id "${instance_id}" --output json > "${invocation_json}" 2>/dev/null; then
      local status
      status="$(python3 - "${invocation_json}" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
print(doc.get("Status", "Unknown"))
PY
)"
      case "${status}" in
        Success)
          python3 - "${invocation_json}" "${DR_KUBECONFIG_RAW}" <<'PY'
import json
import pathlib
import sys

doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
out = str(doc.get("StandardOutputContent", ""))
if not out.strip():
    raise SystemExit("empty StandardOutputContent from SSM kubeconfig fetch")
path = pathlib.Path(sys.argv[2])
path.write_text(out if out.endswith("\n") else out + "\n", encoding="utf-8")
PY
          return 0
          ;;
        Pending|InProgress|Delayed|"")
          ;;
        Failed|TimedOut|Cancelled|Cancelling)
          return 1
          ;;
        *)
          ;;
      esac
    fi
    sleep 5
  done
  return 1
}

patch_kubeconfig_public_endpoint() {
  local source_file="$1"
  local dest_file="$2"
  local public_ip="$3"
  python3 - "${source_file}" "${dest_file}" "${public_ip}" <<'PY'
import ipaddress
import pathlib
import re
import sys
from urllib.parse import urlparse

src, dst, public_ip = sys.argv[1], sys.argv[2], sys.argv[3]
text = pathlib.Path(src).read_text(encoding="utf-8")
lines = text.splitlines()
patched = []
updated = False
skip_tls_indent = None

for line in lines:
    if skip_tls_indent is not None:
        if re.match(rf"^{re.escape(skip_tls_indent)}tls-server-name:\s*\S+\s*$", line):
            skip_tls_indent = None
            continue
        if line.startswith(skip_tls_indent):
            skip_tls_indent = None

    m = re.match(r"^(\s*)server:\s*(\S+)\s*$", line)
    if not m:
        patched.append(line)
        continue
    indent, server = m.group(1), m.group(2)
    host = ""
    try:
        host = urlparse(server).hostname or ""
    except Exception:
        host = ""
    replace = False
    if host in ("localhost", "127.0.0.1", ""):
        replace = True
    else:
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback:
                replace = True
        except ValueError:
            replace = False
    if replace:
        tls_server_name = host if host and host != "localhost" else "127.0.0.1"
        patched.append(f"{indent}server: https://{public_ip}:6443")
        patched.append(f"{indent}tls-server-name: {tls_server_name}")
        skip_tls_indent = indent
        updated = True
    else:
        patched.append(line)

out = "\n".join(patched) + "\n"
pathlib.Path(dst).write_text(out, encoding="utf-8")
print("patched" if updated else "unchanged")
PY
}

validate_kubeconfig_yaml() {
  local kubeconfig_path="$1"
  local validate_log="${RECEIPT_DIR}/kubeconfig.validate.log"
  local invalid_dump="${RECEIPT_DIR}/kubeconfig.invalid.annotated.txt"

  if python3 - "${kubeconfig_path}" > "${validate_log}" 2>&1 <<'PY'
import pathlib
import subprocess
import sys

path = pathlib.Path(sys.argv[1])
proc = subprocess.run(
    ["kubectl", "config", "view", "--raw", "--kubeconfig", str(path)],
    capture_output=True,
    text=True,
)
if proc.returncode != 0:
    msg = (proc.stderr or proc.stdout or "").strip()
    raise SystemExit(msg or "kubeconfig parse failed")
print("kubeconfig_yaml_valid")
PY
  then
    return 0
  fi

  # Receipt the exact generated content with line numbers for diagnosis.
  nl -ba "${kubeconfig_path}" > "${invalid_dump}" || cp "${kubeconfig_path}" "${invalid_dump}"
  fail "generated kubeconfig is invalid YAML; see ${validate_log} and ${invalid_dump}"
}

prepare_kubeconfig() {
  [[ -n "${INSTANCE_ID}" ]] || fail "INSTANCE_ID is empty"
  [[ -n "${PUBLIC_IP}" ]] || fail "PUBLIC_IP is empty"

  wait_for_ssm_online "${INSTANCE_ID}" 420
  fetch_k3s_kubeconfig_from_ssm "${INSTANCE_ID}"
  patch_kubeconfig_public_endpoint "${DR_KUBECONFIG_RAW}" "${DR_KUBECONFIG_PUBLIC}" "${PUBLIC_IP}" > "${RECEIPT_DIR}/kubeconfig.patch.result.txt"
  write_kubeconfig_receipts "bringup_generated" ""
  validate_kubeconfig_yaml "${DR_KUBECONFIG_PUBLIC}"
  HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl get nodes -o wide > "${RECEIPT_DIR}/kubectl.get_nodes.txt"
}

prepare_kubeconfig_from_input() {
  [[ -s "${DR_KUBECONFIG_PUBLIC}" ]] || fail "kubeconfig not found: ${DR_KUBECONFIG_PUBLIC}"
  write_kubeconfig_receipts "${KUBECONFIG_SELECTION_SOURCE}" "${KUBECONFIG_SELECTION_RECEIPT_DIR}"
  validate_kubeconfig_yaml "${DR_KUBECONFIG_PUBLIC}"
  HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl get nodes -o wide > "${RECEIPT_DIR}/kubectl.get_nodes.txt"
}

repair_bringup() {
  note "repair bringup: refreshing TF_VAR_allowed_cidr from current public IP"
  local ip
  ip="$(curl -fsSL https://checkip.amazonaws.com | tr -d '[:space:]')"
  [[ "${ip}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 0
  export TF_VAR_allowed_cidr="${ip}/32"
  note "repair bringup: TF_VAR_allowed_cidr=${TF_VAR_allowed_cidr}"
  return 0
}

repair_restore() {
  note "repair restore: re-running backup contract diagnostic"
  "${ROOT_DIR}/scripts/ops/dr_contract.py" --backup-uri "${BACKUP_URI}" > "${RECEIPT_DIR}/restore.contract.diagnostic.json"
  return 0
}

repair_validate() {
  if [[ -n "${INSTANCE_ID}" && -n "${PUBLIC_IP}" ]]; then
    note "repair validate: refreshing kubeconfig via SSM"
    prepare_kubeconfig
  else
    note "repair validate: skipping kubeconfig refresh (no instance context)"
  fi
  return 0
}

repair_teardown() {
  note "repair teardown: waiting before retry"
  sleep 5
  return 0
}

classify_validate_failure() {
  local attempt="$1"
  local reason="non_retryable"
  local retryable=0
  local combined=""
  local scoped=""
  local validate_receipt_dir="${RECEIPT_DIR}/validate.step"
  local validate_job_name=""
  local validate_pod_name=""
  if [[ -f "${validate_receipt_dir}/validate.job_name.txt" ]]; then
    validate_job_name="$(tr -d '[:space:]' < "${validate_receipt_dir}/validate.job_name.txt" || true)"
  fi
  if [[ -f "${validate_receipt_dir}/dr_validate.pod_name.txt" ]]; then
    validate_pod_name="$(tr -d '[:space:]' < "${validate_receipt_dir}/dr_validate.pod_name.txt" || true)"
  fi
  local artifacts=(
    "${CURRENT_PHASE_LOG}"
    "${validate_receipt_dir}/dr_validate.events.txt"
    "${validate_receipt_dir}/dr_validate.describe_pod.txt"
    "${validate_receipt_dir}/dr_validate.describe_job.txt"
    "${validate_receipt_dir}/dr_validate.wait.log"
  )
  for f in "${artifacts[@]}"; do
    if [[ -f "${f}" ]]; then
      combined+=$'\n'
      combined+="--- ${f} ---"
      combined+=$'\n'
      combined+="$(cat "${f}" 2>/dev/null || true)"
      combined+=$'\n'
    fi
  done
  if [[ -n "${validate_job_name}" || -n "${validate_pod_name}" ]]; then
    scoped="$(printf '%s' "${combined}" | rg -i "${validate_job_name}|${validate_pod_name}" || true)"
  fi
  if [[ -z "${scoped}" ]]; then
    scoped="${combined}"
  fi

  if printf '%s' "${scoped}" | rg -qi 'ErrImagePull|ImagePullBackOff|no basic auth credentials|pull access denied|failed to pull image'; then
    reason="image_pull_auth"
    retryable=1
  elif printf '%s' "${scoped}" | rg -qi 'Insufficient memory|[0-9]+/[0-9]+ nodes are available:.*Insufficient memory'; then
    reason="insufficient_memory"
    retryable=1
  fi

  local out_env="${RECEIPT_DIR}/validate.retry.attempt${attempt}.env"
  local out_json="${RECEIPT_DIR}/validate.retry.attempt${attempt}.json"
  cat > "${out_env}" <<EOF
ATTEMPT=${attempt}
RETRYABLE=${retryable}
REASON=${reason}
MAX_RETRIES=${DR_VALIDATE_MAX_RETRIES}
RETRY_BACKOFF_SECONDS_BASE=${DR_VALIDATE_RETRY_BACKOFF_SECONDS}
EOF
  python3 - "${out_env}" "${out_json}" <<'PY'
import json
import pathlib
import sys

env = {}
for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
payload = {
    "schema_version": 1,
    "attempt": int(env.get("ATTEMPT", "0")),
    "retryable": env.get("RETRYABLE", "0") == "1",
    "reason": env.get("REASON", ""),
    "max_retries": int(env.get("MAX_RETRIES", "0")),
    "retry_backoff_seconds_base": int(env.get("RETRY_BACKOFF_SECONDS_BASE", "0")),
}
pathlib.Path(sys.argv[2]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  printf '%s|%s\n' "${retryable}" "${reason}"
}

phase_bringup() {
  APPLY=1 "${ROOT_DIR}/scripts/ops/dr_bringup.sh"
  terraform -chdir="${ROOT_DIR}/ops/dr/terraform" output -json > "${RECEIPT_DIR}/terraform.outputs.json"
  INSTANCE_ID="$(terraform -chdir="${ROOT_DIR}/ops/dr/terraform" output -raw instance_id)"
  PUBLIC_IP="$(terraform -chdir="${ROOT_DIR}/ops/dr/terraform" output -raw public_ip)"
  [[ -n "${INSTANCE_ID}" && "${INSTANCE_ID}" != "null" ]] || fail "missing terraform output: instance_id"
  [[ -n "${PUBLIC_IP}" && "${PUBLIC_IP}" != "null" ]] || fail "missing terraform output: public_ip"

  aws ec2 wait instance-running --instance-ids "${INSTANCE_ID}"
  aws ec2 wait instance-status-ok --instance-ids "${INSTANCE_ID}"

  aws ec2 describe-instances --instance-ids "${INSTANCE_ID}" --output json > "${RECEIPT_DIR}/ec2.instance.json"
  local root_volume_id=""
  local instance_meta_env="${RECEIPT_DIR}/ec2.instance.meta.env"
  python3 - "${RECEIPT_DIR}/ec2.instance.json" > "${instance_meta_env}" <<'PY'
import json
import sys
d = json.load(open(sys.argv[1], "r", encoding="utf-8"))
inst = d["Reservations"][0]["Instances"][0]
sg = ""
if inst.get("SecurityGroups"):
    sg = inst["SecurityGroups"][0].get("GroupId", "")
root = ""
for mapping in inst.get("BlockDeviceMappings", []):
    dev = mapping.get("DeviceName", "")
    if dev in ("/dev/sda1", "/dev/xvda") and mapping.get("Ebs", {}).get("VolumeId"):
        root = mapping["Ebs"]["VolumeId"]
        break
if not root:
    for mapping in inst.get("BlockDeviceMappings", []):
        if mapping.get("Ebs", {}).get("VolumeId"):
            root = mapping["Ebs"]["VolumeId"]
            break
print(f"SECURITY_GROUP_ID={sg}")
print(f"KEY_NAME={inst.get('KeyName', '')}")
print(f"ACTUAL_INSTANCE_TYPE={inst.get('InstanceType', '')}")
print(f"ROOT_VOLUME_ID={root}")
PY
  # shellcheck disable=SC1090
  source "${instance_meta_env}"
  root_volume_id="${ROOT_VOLUME_ID:-}"
  if [[ -n "${root_volume_id}" ]]; then
    ACTUAL_EBS_ROOT_GB="$(aws ec2 describe-volumes --volume-ids "${root_volume_id}" --query 'Volumes[0].Size' --output text 2>/dev/null || true)"
  fi
  if [[ -z "${ACTUAL_EBS_ROOT_GB}" || "${ACTUAL_EBS_ROOT_GB}" == "None" ]]; then
    ACTUAL_EBS_ROOT_GB="unknown"
  fi
  python3 - "${RECEIPT_DIR}/drill.cost.actual.json" "${ACTUAL_INSTANCE_TYPE}" "${ACTUAL_EBS_ROOT_GB}" "${root_volume_id}" "$(ts)" <<'PY'
import json
import pathlib
import sys

out, instance_type, ebs_root_gb, root_volume_id, ts_utc = sys.argv[1:]
payload = {
    "schema_version": 1,
    "recorded_at_utc": ts_utc,
    "instance_type_actual": instance_type,
    "ebs_root_gb_actual": ebs_root_gb,
    "root_volume_id": root_volume_id,
}
pathlib.Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

  local runner_count
  runner_count="$(aws ec2 describe-instances \
    --filters \
      "Name=tag:Name,Values=jobintel-dr-runner" \
      "Name=tag:Purpose,Values=jobintel-dr" \
      "Name=tag:ManagedBy,Values=terraform" \
      "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query "length(Reservations[].Instances[])" \
    --output text)"
  [[ "${runner_count}" == "1" ]] || fail "expected exactly one DR runner; found=${runner_count}"

  prepare_kubeconfig
}

phase_restore() {
  "${ROOT_DIR}/scripts/ops/dr_restore.sh" \
    --backup-uri "${BACKUP_URI}" \
    --kubeconfig "${DR_KUBECONFIG_PUBLIC}" \
    --namespace "${NAMESPACE}" \
    --image-ref "${IMAGE_REF}"
}

phase_validate() {
  local validate_receipt_dir="${RECEIPT_DIR}/validate.step"
  mkdir -p "${validate_receipt_dir}"
  local validate_skip_workload_assume_env="0"
  if [[ "${VALIDATE_SKIP_WORKLOAD_ASSUME}" == "true" ]]; then
    validate_skip_workload_assume_env="1"
  fi
  cat > "${validate_receipt_dir}/dr_drill.validate_mode.env" <<EOF
VALIDATE_SKIP_WORKLOAD_ASSUME=${validate_skip_workload_assume_env}
VALIDATION_MODE=$([[ "${validate_skip_workload_assume_env}" == "1" ]] && echo "skip_workload_assume" || echo "strict_workload")
EOF
  local cp_bucket=""
  local cp_prefix=""
  read -r cp_bucket cp_prefix <<<"$(python3 - "${BACKUP_URI}" <<'PY'
import sys
uri = sys.argv[1]
if not uri.startswith("s3://"):
    print("", "")
    raise SystemExit(0)
payload = uri[len("s3://"):]
bucket, _, key = payload.partition("/")
key = key.strip("/")
needle = "/backups/"
prefix = ""
if needle in key:
    prefix = key.split(needle, 1)[0].strip("/")
elif key.endswith("/backups"):
    prefix = key[:-len("/backups")].strip("/")
print(bucket, prefix)
PY
)"
  XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" get all \
    > "${validate_receipt_dir}/dr_drill.prevalidate.get_all.txt" 2>&1 || true
  XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" get cronjob -o wide \
    > "${validate_receipt_dir}/dr_drill.prevalidate.get_cronjob_wide.txt" 2>&1 || true
  XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" get cm,secret -o name \
    > "${validate_receipt_dir}/dr_drill.prevalidate.get_cm_secret_name.txt" 2>&1 || true
  if [[ -n "${IMAGE_REF}" ]]; then
    RECEIPT_DIR="${validate_receipt_dir}" \
    CHECK_IMAGE_ONLY=1 \
    CHECK_ARCH=arm64 \
    CONTROL_PLANE_BUCKET="${cp_bucket}" \
    CONTROL_PLANE_PREFIX="${cp_prefix}" \
    VALIDATE_SKIP_WORKLOAD_ASSUME="${validate_skip_workload_assume_env}" \
    IMAGE_REF="${IMAGE_REF}" \
    ALLOW_TAG=$([[ "${ALLOW_TAG}" == "true" ]] && echo "1" || echo "0") \
    "${ROOT_DIR}/scripts/ops/dr_validate.sh" || return $?
  fi

  XDG_CACHE_HOME="${KUBE_HOME}" \
  KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" \
  RUN_JOB=1 \
  NAMESPACE="${NAMESPACE}" \
  CONTROL_PLANE_BUCKET="${cp_bucket}" \
  CONTROL_PLANE_PREFIX="${cp_prefix}" \
  VALIDATE_SKIP_WORKLOAD_ASSUME="${validate_skip_workload_assume_env}" \
  IMAGE_REF="${IMAGE_REF}" \
  ALLOW_TAG=$([[ "${ALLOW_TAG}" == "true" ]] && echo "1" || echo "0") \
  RECEIPT_DIR="${validate_receipt_dir}" \
  "${ROOT_DIR}/scripts/ops/dr_validate.sh" || return $?

  DR_JOB_NAME=""
  if [[ -f "${validate_receipt_dir}/validate.job_name.txt" ]]; then
    DR_JOB_NAME="$(tr -d '[:space:]' < "${validate_receipt_dir}/validate.job_name.txt" || true)"
  fi
  if [[ -z "${DR_JOB_NAME}" && -f "${validate_receipt_dir}/dr_validate.job_name.txt" ]]; then
    DR_JOB_NAME="$(sed -n 's/^DR_JOB_NAME=//p' "${validate_receipt_dir}/dr_validate.job_name.txt" | tail -n 1 | tr -d '[:space:]' || true)"
  fi
  if [[ -z "${DR_JOB_NAME}" ]]; then
    DR_JOB_NAME="$(sed -n 's/^DR_JOB_NAME=//p' "${CURRENT_PHASE_LOG}" | tail -n 1 || true)"
  fi
  if [[ -z "${DR_JOB_NAME}" ]]; then
    DR_JOB_NAME="$(XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" get jobs -o name \
      | sed 's#job.batch/##' \
      | rg '^jobintel-dr-validate-' \
      | tail -n 1 || true)"
  fi
  if [[ -z "${DR_JOB_NAME}" ]]; then
    echo "[FAIL] unable to resolve DR validate job name" >&2
    return 1
  fi

  DR_RUN_ID=""
  if [[ -f "${validate_receipt_dir}/validate.run_id.txt" ]]; then
    DR_RUN_ID="$(tr -d '[:space:]' < "${validate_receipt_dir}/validate.run_id.txt" || true)"
  fi
  XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" logs "job/${DR_JOB_NAME}" > "${RECEIPT_DIR}/validate.job.log" || return $?
  if [[ -z "${DR_RUN_ID}" ]]; then
    DR_RUN_ID="$(sed -n 's/.*JOBINTEL_RUN_ID=//p' "${RECEIPT_DIR}/validate.job.log" | head -n 1 | tr -d '[:space:]' || true)"
  fi
}

phase_diagnostics() {
  local diag_dir="${RECEIPT_DIR}/diagnostics.step"
  mkdir -p "${diag_dir}"
  XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl get nodes -o wide \
    > "${diag_dir}/kubectl.get_nodes.txt" 2>&1
  XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" get all \
    > "${diag_dir}/kubectl.get_all.txt" 2>&1 || true
  XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" get cronjob -o wide \
    > "${diag_dir}/kubectl.get_cronjob_wide.txt" 2>&1 || true
  XDG_CACHE_HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" get cm,secret -o name \
    > "${diag_dir}/kubectl.get_cm_secret_name.txt" 2>&1 || true
}

phase_promote() {
  [[ "${AUTO_PROMOTE}" == "true" ]] || fail "internal error: phase_promote called while auto promote disabled"
  [[ "${ALLOW_PROMOTE_BYPASS}" == "true" ]] || fail "auto promote requested but manual bypass is not explicitly allowed"
  python3 - "${RECEIPT_DIR}" "${DR_RUN_ID}" "${IMAGE_REF}" "${BACKUP_URI}" "${INSTANCE_ID}" "${PUBLIC_IP}" "${NAMESPACE}" <<'PY'
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

receipt_dir, run_id, image_ref, backup_uri, instance_id, public_ip, namespace = sys.argv[1:]
payload = {
    "schema_version": 1,
    "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "mode": "dr_drill_manual_bypass",
    "approved": True,
    "auto_promote": True,
    "manual_bypass_allowed": True,
    "approver": os.environ.get("USER", "unknown"),
    "ticket": "",
    "dr_run_id": run_id,
    "image_ref": image_ref,
    "backup_uri": backup_uri,
    "instance_id": instance_id,
    "public_ip": public_ip,
    "namespace": namespace,
    "promotion_status": "approved_but_auto_promote_disabled",
}
pathlib.Path(receipt_dir, "promote.decision.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

verify_zero_dr_runners() {
  local out
  out="$(aws ec2 describe-instances \
    --filters \
      "Name=tag:Name,Values=jobintel-dr-runner" \
      "Name=tag:Purpose,Values=jobintel-dr" \
      "Name=tag:ManagedBy,Values=terraform" \
      "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --output json)"
  printf '%s\n' "${out}" > "${RECEIPT_DIR}/teardown.runners.check.json"
  local count
  count="$(python3 - "${out}" <<'PY'
import json
import sys
d = json.loads(sys.argv[1])
instances = []
for r in d.get("Reservations", []):
    instances.extend(r.get("Instances", []))
print(len(instances))
PY
)"
  [[ "${count}" == "0" ]] || fail "teardown verification failed; remaining DR runners=${count}"
}

phase_teardown() {
  CONFIRM_DESTROY=1 "${ROOT_DIR}/scripts/ops/dr_teardown.sh"
  verify_zero_dr_runners
}

run_phase() {
  local phase="$1"
  local phase_fn="$2"
  local repair_fn="$3"
  local command_hint="$4"
  local started_at
  started_at="$(ts)"
  local attempts=0
  local max_attempts="${MAX_PHASE_ATTEMPTS}"
  if [[ "${phase}" == "validate" ]]; then
    local validate_cap=$((DR_VALIDATE_MAX_RETRIES + 1))
    if (( validate_cap < max_attempts )); then
      max_attempts="${validate_cap}"
    fi
  fi
  local repaired=0
  local last_log=""
  local last_error=""

  note "phase=${phase} start"
  while (( attempts < max_attempts )); do
    attempts=$((attempts + 1))
    CURRENT_PHASE_LOG="${RECEIPT_DIR}/${phase}.attempt${attempts}.log"
    last_log="${CURRENT_PHASE_LOG}"

    local rc=0
    if "${phase_fn}" > "${CURRENT_PHASE_LOG}" 2>&1; then
      rc=0
    else
      rc=$?
    fi

    if [[ "${rc}" -eq 0 ]]; then
      write_phase_receipt "${phase}" "success" "${attempts}" "${repaired}" "${command_hint}" "${last_log}" "" "${started_at}" "$(ts)"
      note "phase=${phase} status=success attempts=${attempts}"
      return 0
    fi

    last_error="$(tail -n 60 "${CURRENT_PHASE_LOG}" || true)"
    echo "[FAIL] phase=${phase} attempt=${attempts}/${max_attempts} rc=${rc}" >&2
    echo "[FAIL] command=${command_hint}" >&2
    echo "[FAIL] stderr_tail:" >&2
    echo "${last_error}" >&2

    if [[ "${phase}" == "validate" ]]; then
      local validate_retryable=0
      local validate_reason="non_retryable"
      IFS='|' read -r validate_retryable validate_reason <<<"$(classify_validate_failure "${attempts}")"
      note "phase=validate retryability reason=${validate_reason} retryable=${validate_retryable}"
      if [[ "${validate_retryable}" != "1" ]]; then
        write_phase_receipt "${phase}" "failed" "${attempts}" "${repaired}" "${command_hint}" "${last_log}" "${last_error}" "${started_at}" "$(ts)"
        FAILED_PHASE="${phase}"
        FAILED_ERROR="${last_error}"
        OVERALL_STATUS="failed"
        mark_stop_reason "phase=${phase} failed (non-retryable)"
        return 1
      fi
      if (( attempts >= max_attempts )); then
        break
      fi
      local backoff_seconds=$((DR_VALIDATE_RETRY_BACKOFF_SECONDS * attempts))
      if (( backoff_seconds > 0 )); then
        note "phase=validate retry_backoff_seconds=${backoff_seconds}"
        sleep "${backoff_seconds}"
      fi
    fi

    if [[ "${repaired}" -eq 0 && -n "${repair_fn}" ]]; then
      set +e
      "${repair_fn}" > "${RECEIPT_DIR}/${phase}.repair.log" 2>&1
      local repair_rc=$?
      set -e
      repaired=1
      note "phase=${phase} repair_attempted rc=${repair_rc}"
    fi
  done

  write_phase_receipt "${phase}" "failed" "${attempts}" "${repaired}" "${command_hint}" "${last_log}" "${last_error}" "${started_at}" "$(ts)"
  FAILED_PHASE="${phase}"
  FAILED_ERROR="${last_error}"
  OVERALL_STATUS="failed"
  mark_stop_reason "phase=${phase} failed after ${attempts} attempts"
  return 1
}

export TF_VAR_region="${AWS_REGION}"
if [[ "${REQUIRES_TERRAFORM_MUTATION}" -eq 1 && -z "${TF_VAR_allowed_cidr:-}" && "${MY_IP}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  export TF_VAR_allowed_cidr="${MY_IP}/32"
fi

MAIN_FAILED=0
WINDOW_SKIP_REASON="outside execution window start-at=${START_AT} stop-after=${STOP_AFTER}"

if [[ "${RUN_BRINGUP}" -eq 0 && ( "${RUN_RESTORE}" -eq 1 || "${RUN_VALIDATE}" -eq 1 || "${RUN_DIAGNOSTICS}" -eq 1 ) ]]; then
  prepare_kubeconfig_from_input
fi

run_or_skip_phase() {
  local phase="$1"
  local enabled="$2"
  local phase_fn="$3"
  local repair_fn="$4"
  local command_hint="$5"
  local disabled_reason="$6"

  if [[ "${MAIN_FAILED}" -ne 0 ]]; then
    write_skipped_phase "${phase}" "skipped due upstream failure in phase=${FAILED_PHASE}"
    return 0
  fi
  if [[ "${enabled}" -ne 1 ]]; then
    write_skipped_phase "${phase}" "${disabled_reason}"
    return 0
  fi
  run_phase "${phase}" "${phase_fn}" "${repair_fn}" "${command_hint}" || MAIN_FAILED=1
}

run_or_skip_phase "bringup" "${RUN_BRINGUP}" phase_bringup repair_bringup "APPLY=1 scripts/ops/dr_bringup.sh" "${WINDOW_SKIP_REASON}"
run_or_skip_phase "restore" "${RUN_RESTORE}" phase_restore repair_restore "scripts/ops/dr_restore.sh --backup-uri <backup_uri>" "${WINDOW_SKIP_REASON}"
run_or_skip_phase "validate" "${RUN_VALIDATE}" phase_validate repair_validate "RUN_JOB=1 scripts/ops/dr_validate.sh" "${WINDOW_SKIP_REASON}"
run_or_skip_phase "diagnostics" "${RUN_DIAGNOSTICS}" phase_diagnostics "" "kubectl cluster diagnostics snapshot" "diagnostics-only mode not enabled"

if [[ "${MAIN_FAILED}" -ne 0 ]]; then
  write_skipped_phase "promote" "skipped due upstream failure in phase=${FAILED_PHASE}"
elif [[ "${RUN_PROMOTE}" -ne 1 ]]; then
  write_skipped_phase "promote" "${WINDOW_SKIP_REASON}"
elif [[ "${AUTO_PROMOTE}" != "true" ]]; then
  write_skipped_phase "promote" "auto promote disabled"
  mark_stop_reason "auto promote disabled; stopped at manual promotion gate"
else
  run_phase "promote" phase_promote "" "promote decision (manual bypass gated)" || MAIN_FAILED=1
fi

if [[ "${TEARDOWN}" == "true" ]]; then
  if ! run_phase "teardown" phase_teardown repair_teardown "CONFIRM_DESTROY=1 scripts/ops/dr_teardown.sh"; then
    MAIN_FAILED=1
  fi
else
  write_skipped_phase "teardown" "teardown disabled by flag"
fi

if [[ "${MAIN_FAILED}" -ne 0 ]]; then
  OVERALL_STATUS="failed"
  exit 1
fi

if [[ -z "${STOP_REASON}" ]]; then
  if [[ "${DIAGNOSTICS_ONLY}" == "true" ]]; then
    mark_stop_reason "diagnostics-only mode completed"
  elif [[ "${START_AT}" == "teardown" ]]; then
    if [[ "${TEARDOWN}" == "true" ]]; then
      mark_stop_reason "start-at=teardown executed teardown only"
    else
      mark_stop_reason "start-at=teardown with teardown disabled (no execution)"
    fi
  elif [[ "${STOP_AFTER}" != "promote" ]]; then
    mark_stop_reason "stop-after=${STOP_AFTER} reached"
  else
    mark_stop_reason "completed requested phases"
  fi
fi

OVERALL_STATUS="success"
exit 0
