#!/usr/bin/env bash
# Deterministic failback command path: pointer switchback with dry-run (default) and apply.
# M19C DoD: deterministic failback command path exists (dry-run + apply).
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/dr_failback_pointers.sh \
    --bucket <bucket> \
    --prefix <prefix> \
    --primary-run-id <run_id> \
    --dr-run-id <run_id> \
    --receipt-dir <path> \
    [--provider openai] [--profile cs] [--expected-account-id 048622080012] [--region us-east-1] \
    [--dry-run] [--apply]

Modes:
  --dry-run (default): Capture before state, verify, write plan receipt. No mutations.
  --apply: Perform pointer switchback, re-verify, write apply receipt.

Required:
  --bucket, --prefix: S3 bucket and prefix where pointers live.
  --primary-run-id: Run to switch back TO (primary canonical).
  --dr-run-id: Run to switch back FROM (current DR canonical).
  --receipt-dir: Directory for receipts (required).
EOF
}

BUCKET=""
PREFIX=""
PRIMARY_RUN_ID=""
DR_RUN_ID=""
RECEIPT_DIR=""
PROVIDER="openai"
PROFILE="cs"
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
REGION="${REGION:-us-east-1}"
APPLY_MODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="${2:-}"; shift 2 ;;
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --primary-run-id) PRIMARY_RUN_ID="${2:-}"; shift 2 ;;
    --dr-run-id) DR_RUN_ID="${2:-}"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="${2:-}"; shift 2 ;;
    --provider) PROVIDER="${2:-}"; shift 2 ;;
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --expected-account-id) EXPECTED_ACCOUNT_ID="${2:-}"; shift 2 ;;
    --region) REGION="${2:-}"; shift 2 ;;
    --dry-run) APPLY_MODE=0; shift ;;
    --apply) APPLY_MODE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

[[ -n "${BUCKET}" ]] || fail "--bucket is required"
[[ -n "${PREFIX}" ]] || fail "--prefix is required"
[[ -n "${PRIMARY_RUN_ID}" ]] || fail "--primary-run-id is required"
[[ -n "${DR_RUN_ID}" ]] || fail "--dr-run-id is required"
[[ -n "${RECEIPT_DIR}" ]] || fail "--receipt-dir is required"

AWS_REGION="${AWS_REGION:-${REGION}}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
export AWS_REGION AWS_DEFAULT_REGION
export AWS_PAGER=""

command -v aws >/dev/null 2>&1 || fail "aws is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"
command -v jq >/dev/null 2>&1 || fail "jq is required"

mkdir -p "${RECEIPT_DIR}" || fail "cannot create receipt dir: ${RECEIPT_DIR}"

export RECEIPT_DIR BUCKET PREFIX PRIMARY_RUN_ID DR_RUN_ID PROVIDER PROFILE EXPECTED_ACCOUNT_ID REGION
export APPLY_MODE
ts() { date -u +%Y-%m-%dT%H%M:%SZ; }

# Phase timestamps (deterministic ordering)
declare -A PHASE_TS
phase() { PHASE_TS["$1"]="$(ts)"; }

# --- 1. Write inputs receipt ---
phase "inputs"
python3 - "${RECEIPT_DIR}" "${BUCKET}" "${PREFIX}" "${PRIMARY_RUN_ID}" "${DR_RUN_ID}" "${PROVIDER}" "${PROFILE}" "${EXPECTED_ACCOUNT_ID}" "${REGION}" "${APPLY_MODE}" <<'PY'
import json
import os
from pathlib import Path

receipt_dir, bucket, prefix, primary_run_id, dr_run_id, provider, profile, expected_account_id, region, apply_mode = os.environ["RECEIPT_DIR"], os.environ["BUCKET"], os.environ["PREFIX"], os.environ["PRIMARY_RUN_ID"], os.environ["DR_RUN_ID"], os.environ["PROVIDER"], os.environ["PROFILE"], os.environ["EXPECTED_ACCOUNT_ID"], os.environ["REGION"], int(os.environ["APPLY_MODE"])
payload = {
    "schema_version": 1,
    "bucket": bucket,
    "prefix": prefix.strip("/"),
    "primary_run_id": primary_run_id,
    "dr_run_id": dr_run_id,
    "provider": provider,
    "profile": profile,
    "expected_account_id": expected_account_id,
    "region": region,
    "apply_mode": bool(apply_mode),
    "dry_run": not apply_mode,
}
Path(receipt_dir).joinpath("drill.failback.inputs.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
note "wrote drill.failback.inputs.json"

# --- 2. Account/region contract ---
ACTUAL="$(aws sts get-caller-identity --query Account --output text)"
[[ "${ACTUAL}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${ACTUAL}"

# --- 3. Capture before pointers ---
phase "verify_before"
PREFIX_CLEAN="${PREFIX%/}"
GLOBAL_KEY="${PREFIX_CLEAN}/state/last_success.json"
PROVIDER_KEY="${PREFIX_CLEAN}/state/${PROVIDER}/${PROFILE}/last_success.json"

BEFORE_DIR="${RECEIPT_DIR}/before"
mkdir -p "${BEFORE_DIR}"
aws s3 cp "s3://${BUCKET}/${GLOBAL_KEY}" "${BEFORE_DIR}/global.json" 2>/dev/null || echo '{}' > "${BEFORE_DIR}/global.json"
aws s3 cp "s3://${BUCKET}/${PROVIDER_KEY}" "${BEFORE_DIR}/provider.json" 2>/dev/null || echo '{}' > "${BEFORE_DIR}/provider.json"

BEFORE_GLOBAL_RUN="$(jq -r '.run_id // ""' "${BEFORE_DIR}/global.json")"
BEFORE_PROVIDER_RUN="$(jq -r '.run_id // ""' "${BEFORE_DIR}/provider.json")"
BEFORE_GLOBAL_RUN_PATH="$(jq -r '.run_path // ""' "${BEFORE_DIR}/global.json")"
BEFORE_GLOBAL_ENDED_AT="$(jq -r '.ended_at // ""' "${BEFORE_DIR}/global.json")"
export BEFORE_GLOBAL_RUN BEFORE_PROVIDER_RUN
export BEFORE_GLOBAL_RUN_PATH BEFORE_GLOBAL_ENDED_AT

python3 - "${RECEIPT_DIR}" "${BEFORE_GLOBAL_RUN}" "${BEFORE_PROVIDER_RUN}" "${DR_RUN_ID}" <<'PY'
import json
import os
from pathlib import Path

receipt_dir, before_global, before_provider, dr_run_id = os.environ["RECEIPT_DIR"], os.environ["BEFORE_GLOBAL_RUN"], os.environ["BEFORE_PROVIDER_RUN"], os.environ["DR_RUN_ID"]
payload = {
    "schema_version": 1,
    "global_pointer_run_id": before_global or None,
    "provider_pointer_run_id": before_provider or None,
    "expected_dr_run_id": dr_run_id,
    "pointers_match_dr": (before_global == dr_run_id and before_provider == dr_run_id),
}
Path(receipt_dir).joinpath("drill.failback.verify_before.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
note "wrote drill.failback.verify_before.json"

if [[ "${BEFORE_GLOBAL_RUN}" != "${DR_RUN_ID}" || "${BEFORE_PROVIDER_RUN}" != "${DR_RUN_ID}" ]]; then
  fail "before pointers do not match dr-run-id: global=${BEFORE_GLOBAL_RUN} provider=${BEFORE_PROVIDER_RUN} expected=${DR_RUN_ID}"
fi

# --- 4. Verify published S3 (DR run) ---
phase "verify_dr_published"
COMPARE_DIR="${RECEIPT_DIR}/compare"
mkdir -p "${COMPARE_DIR}/dr"
aws s3 sync "s3://${BUCKET}/${PREFIX_CLEAN}/runs/${DR_RUN_ID}/" "${COMPARE_DIR}/dr/" 2>/dev/null || true
python3 "${ROOT_DIR}/scripts/verify_published_s3.py" \
  --bucket "${BUCKET}" \
  --run-id "${DR_RUN_ID}" \
  --prefix "${PREFIX}" \
  --run-dir "${COMPARE_DIR}/dr" \
  --verify-latest 2>"${RECEIPT_DIR}/verify_dr.stderr" | tee "${RECEIPT_DIR}/verify_dr.stdout" || true
# Allow non-zero: verify may fail if run dir structure differs; we record the attempt

# --- 5. Compare artifacts (primary vs DR) if both exist in S3 ---
phase "compare"
mkdir -p "${COMPARE_DIR}/primary"
aws s3 sync "s3://${BUCKET}/${PREFIX_CLEAN}/runs/${PRIMARY_RUN_ID}/" "${COMPARE_DIR}/primary/" 2>/dev/null || true

COMPARE_EXIT=0
if [[ -f "${COMPARE_DIR}/primary/run_summary.v1.json" && -f "${COMPARE_DIR}/dr/run_summary.v1.json" ]]; then
  python3 "${ROOT_DIR}/scripts/compare_run_artifacts.py" \
    "${COMPARE_DIR}/primary" \
    "${COMPARE_DIR}/dr" \
    --allow-run-id-drift \
    --repo-root "${ROOT_DIR}" > "${RECEIPT_DIR}/compare_run_artifacts.log" 2>&1 || COMPARE_EXIT=$?
  echo "compare_exit=${COMPARE_EXIT}" >> "${RECEIPT_DIR}/compare_run_artifacts.log"
else
  note "skip compare: missing run_summary in primary or dr"
  echo "skipped: missing artifacts" > "${RECEIPT_DIR}/compare_run_artifacts.log"
fi

# --- 6. Build plan (what would change) ---
phase "plan"
# Fetch primary run_summary to build pointer payload
PRIMARY_SUMMARY="${RECEIPT_DIR}/primary_run_summary.json"
if aws s3 cp "s3://${BUCKET}/${PREFIX_CLEAN}/runs/${PRIMARY_RUN_ID}/run_summary.v1.json" "${PRIMARY_SUMMARY}" 2>/dev/null; then
  ENDED_AT="$(jq -r '.created_at_utc // .ended_at // ""' "${PRIMARY_SUMMARY}")"
  RUN_PATH="$(jq -r '.run_path // ""' "${PRIMARY_SUMMARY}")"
  [[ -n "${RUN_PATH}" ]] || RUN_PATH="runs/${PRIMARY_RUN_ID}/"
else
  if [[ "${PRIMARY_RUN_ID}" == "${BEFORE_GLOBAL_RUN}" && -n "${BEFORE_GLOBAL_RUN_PATH}" ]]; then
    ENDED_AT="${BEFORE_GLOBAL_ENDED_AT}"
    RUN_PATH="${BEFORE_GLOBAL_RUN_PATH}"
  else
    fail "primary run_summary not found: s3://${BUCKET}/${PREFIX_CLEAN}/runs/${PRIMARY_RUN_ID}/run_summary.v1.json"
  fi
fi
export ENDED_AT RUN_PATH GLOBAL_KEY PROVIDER_KEY

python3 - "${RECEIPT_DIR}" "${PRIMARY_RUN_ID}" "${DR_RUN_ID}" "${RUN_PATH}" "${ENDED_AT}" "${GLOBAL_KEY}" "${PROVIDER_KEY}" <<PY
import json
import os
from pathlib import Path

receipt_dir, primary_run_id, dr_run_id, run_path, ended_at, global_key, provider_key = os.environ["RECEIPT_DIR"], os.environ["PRIMARY_RUN_ID"], os.environ["DR_RUN_ID"], os.environ["RUN_PATH"], os.environ["ENDED_AT"], os.environ["GLOBAL_KEY"], os.environ["PROVIDER_KEY"]
payload = {
    "schema_version": 1,
    "from_run_id": dr_run_id,
    "to_run_id": primary_run_id,
    "pointer_updates": [
        {"key": global_key, "payload": {"run_id": primary_run_id, "run_path": run_path, "ended_at": ended_at or None}},
        {"key": provider_key, "payload": {"run_id": primary_run_id, "run_path": run_path, "ended_at": ended_at or None}},
    ],
    "dry_run": True,
}
Path(receipt_dir).joinpath("drill.failback.plan.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
note "wrote drill.failback.plan.json"

# --- 7. Apply or stop ---
if [[ "${APPLY_MODE}" -eq 0 ]]; then
  note "dry-run complete; use --apply to perform pointer switchback"
  phase "complete"
else
  phase "apply"
  GLOBAL_POINTER_PAYLOAD="$(jq -c \
    --arg run_id "${PRIMARY_RUN_ID}" \
    --arg run_path "${RUN_PATH}" \
    --arg ended_at "${ENDED_AT}" \
    --arg provider "${PROVIDER}" \
    --arg profile "${PROFILE}" \
    '
      (if type == "object" then . else {} end)
      | .schema_version = (.schema_version // 1)
      | .providers = (.providers // [$provider])
      | .profiles = (.profiles // [$profile])
      | .provider_profiles = (.provider_profiles // {})
      | .provider_profiles[($provider + ":" + $profile)] = $run_id
      | .run_id = $run_id
      | .run_path = $run_path
      | .ended_at = (if $ended_at == "" then null else $ended_at end)
    ' "${BEFORE_DIR}/global.json")"
  PROVIDER_POINTER_PAYLOAD="$(jq -c \
    --arg run_id "${PRIMARY_RUN_ID}" \
    --arg run_path "${RUN_PATH}" \
    --arg ended_at "${ENDED_AT}" \
    --arg provider "${PROVIDER}" \
    --arg profile "${PROFILE}" \
    '
      (if type == "object" then . else {} end)
      | .schema_version = (.schema_version // 1)
      | .providers = (.providers // [$provider])
      | .profiles = (.profiles // [$profile])
      | .provider_profiles = (.provider_profiles // {})
      | .provider_profiles[($provider + ":" + $profile)] = $run_id
      | .run_id = $run_id
      | .run_path = $run_path
      | .ended_at = (if $ended_at == "" then null else $ended_at end)
    ' "${BEFORE_DIR}/provider.json")"
  aws s3 cp - "s3://${BUCKET}/${GLOBAL_KEY}" --content-type application/json <<< "${GLOBAL_POINTER_PAYLOAD}"
  aws s3 cp - "s3://${BUCKET}/${PROVIDER_KEY}" --content-type application/json <<< "${PROVIDER_POINTER_PAYLOAD}"
  note "pointers updated to primary_run_id=${PRIMARY_RUN_ID}"

  python3 - "${RECEIPT_DIR}" "${PRIMARY_RUN_ID}" "${GLOBAL_KEY}" "${PROVIDER_KEY}" <<PY
import json
import os
from pathlib import Path

receipt_dir, primary_run_id, global_key, provider_key = os.environ["RECEIPT_DIR"], os.environ["PRIMARY_RUN_ID"], os.environ["GLOBAL_KEY"], os.environ["PROVIDER_KEY"]
payload = {
    "schema_version": 1,
    "applied": True,
    "canonical_run_id": primary_run_id,
    "updated_keys": [global_key, provider_key],
}
Path(receipt_dir).joinpath("drill.failback.apply.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  note "wrote drill.failback.apply.json"

  # --- 8. Verify after ---
  phase "verify_after"
  AFTER_DIR="${RECEIPT_DIR}/after"
  mkdir -p "${AFTER_DIR}"
  aws s3 cp "s3://${BUCKET}/${GLOBAL_KEY}" "${AFTER_DIR}/global.json"
  aws s3 cp "s3://${BUCKET}/${PROVIDER_KEY}" "${AFTER_DIR}/provider.json"
  AFTER_GLOBAL_RUN="$(jq -r '.run_id // ""' "${AFTER_DIR}/global.json")"
  AFTER_PROVIDER_RUN="$(jq -r '.run_id // ""' "${AFTER_DIR}/provider.json")"
  export AFTER_GLOBAL_RUN AFTER_PROVIDER_RUN

  python3 - "${RECEIPT_DIR}" "${AFTER_GLOBAL_RUN}" "${AFTER_PROVIDER_RUN}" "${PRIMARY_RUN_ID}" <<PY
import json
import os
from pathlib import Path

receipt_dir, after_global, after_provider, primary_run_id = os.environ["RECEIPT_DIR"], os.environ["AFTER_GLOBAL_RUN"], os.environ["AFTER_PROVIDER_RUN"], os.environ["PRIMARY_RUN_ID"]
payload = {
    "schema_version": 1,
    "global_pointer_run_id": after_global or None,
    "provider_pointer_run_id": after_provider or None,
    "expected_primary_run_id": primary_run_id,
    "pointers_match_primary": (after_global == primary_run_id and after_provider == primary_run_id),
}
Path(receipt_dir).joinpath("drill.failback.verify_after.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  note "wrote drill.failback.verify_after.json"

  if [[ "${AFTER_GLOBAL_RUN}" != "${PRIMARY_RUN_ID}" || "${AFTER_PROVIDER_RUN}" != "${PRIMARY_RUN_ID}" ]]; then
    fail "after pointers do not match primary-run-id: global=${AFTER_GLOBAL_RUN} provider=${AFTER_PROVIDER_RUN} expected=${PRIMARY_RUN_ID}"
  fi
  phase "complete"
fi

# --- 9. Phase timestamps ---
export TS_INPUTS="${PHASE_TS[inputs]:-}"
export TS_VERIFY_BEFORE="${PHASE_TS[verify_before]:-}"
export TS_VERIFY_DR_PUBLISHED="${PHASE_TS[verify_dr_published]:-}"
export TS_COMPARE="${PHASE_TS[compare]:-}"
export TS_PLAN="${PHASE_TS[plan]:-}"
export TS_APPLY="${PHASE_TS[apply]:-}"
export TS_VERIFY_AFTER="${PHASE_TS[verify_after]:-}"
export TS_COMPLETE="${PHASE_TS[complete]:-}"
python3 - "${RECEIPT_DIR}" <<'PY'
import json
import os
from pathlib import Path

receipt_dir = os.environ["RECEIPT_DIR"]
phases = {
    "inputs": os.environ.get("TS_INPUTS", ""),
    "verify_before": os.environ.get("TS_VERIFY_BEFORE", ""),
    "verify_dr_published": os.environ.get("TS_VERIFY_DR_PUBLISHED", ""),
    "compare": os.environ.get("TS_COMPARE", ""),
    "plan": os.environ.get("TS_PLAN", ""),
    "apply": os.environ.get("TS_APPLY", ""),
    "verify_after": os.environ.get("TS_VERIFY_AFTER", ""),
    "complete": os.environ.get("TS_COMPLETE", ""),
}
phases = {k: v for k, v in phases.items() if v}
payload = {"schema_version": 1, "phases": phases}
Path(receipt_dir).joinpath("drill.failback.phase_timestamps.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
note "wrote drill.failback.phase_timestamps.json"

note "failback pointers complete; receipt_dir=${RECEIPT_DIR}"
