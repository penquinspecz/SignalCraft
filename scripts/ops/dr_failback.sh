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
  scripts/ops/dr_failback.sh \
    --bucket <bucket> \
    --prefix <prefix> \
    --dr-run-id <run_id> \
    --kubeconfig-dr <path> \
    --kubeconfig-primary <path> \
    [--image-ref <repo>@sha256:<digest>|<repo>:<tag>] \
    [--namespace jobintel] \
    [--provider openai] \
    [--profile cs] \
    [--primary-restore-backup-uri s3://<bucket>/<prefix>/backups/<backup_id>] \
    [--sync-src-prefix <prefix>] \
    [--sync-dst-prefix <prefix>] \
    [--teardown true|false] \
    [--confirm1 FAILBACK] \
    [--confirm2 CONFIRM-<dr-run-id>] \
    [--dry-run]

Notes:
  - Requires two confirmations (interactive or via --confirm1/--confirm2).
  - Verifies DR promoted via S3 pointers before failback.
  - Verifies no divergence via scripts/compare_run_artifacts.py.
  - Default tears down DR infra after successful failback checks.
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

BUCKET=""
PREFIX=""
DR_RUN_ID=""
KUBECONFIG_DR=""
KUBECONFIG_PRIMARY=""
IMAGE_REF=""
NAMESPACE="jobintel"
PROVIDER="openai"
PROFILE="cs"
PRIMARY_RESTORE_BACKUP_URI=""
SYNC_SRC_PREFIX=""
SYNC_DST_PREFIX=""
TEARDOWN_RAW="true"
CONFIRM1=""
CONFIRM2=""
DRY_RUN="false"
RECEIPT_DIR=""
ALLOW_TAG="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="${2:-}"; shift 2 ;;
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --dr-run-id) DR_RUN_ID="${2:-}"; shift 2 ;;
    --kubeconfig-dr) KUBECONFIG_DR="${2:-}"; shift 2 ;;
    --kubeconfig-primary) KUBECONFIG_PRIMARY="${2:-}"; shift 2 ;;
    --image-ref) IMAGE_REF="${2:-}"; shift 2 ;;
    --namespace) NAMESPACE="${2:-}"; shift 2 ;;
    --provider) PROVIDER="${2:-}"; shift 2 ;;
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --primary-restore-backup-uri) PRIMARY_RESTORE_BACKUP_URI="${2:-}"; shift 2 ;;
    --sync-src-prefix) SYNC_SRC_PREFIX="${2:-}"; shift 2 ;;
    --sync-dst-prefix) SYNC_DST_PREFIX="${2:-}"; shift 2 ;;
    --teardown) TEARDOWN_RAW="${2:-}"; shift 2 ;;
    --confirm1) CONFIRM1="${2:-}"; shift 2 ;;
    --confirm2) CONFIRM2="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN="true"; shift ;;
    --receipt-dir) RECEIPT_DIR="${2:-}"; shift 2 ;;
    --allow-tag) ALLOW_TAG="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

[[ -n "${BUCKET}" ]] || fail "--bucket is required"
[[ -n "${PREFIX}" ]] || fail "--prefix is required"
[[ -n "${DR_RUN_ID}" ]] || fail "--dr-run-id is required"
[[ -n "${KUBECONFIG_DR}" ]] || fail "--kubeconfig-dr is required"
[[ -n "${KUBECONFIG_PRIMARY}" ]] || fail "--kubeconfig-primary is required"
TEARDOWN="$(parse_bool "${TEARDOWN_RAW}")" || fail "invalid --teardown value: ${TEARDOWN_RAW}"

# M19A: When IMAGE_REF is provided, require digest pinning unless --allow-tag
if [[ -n "${IMAGE_REF}" ]]; then
  allow_tag_arg=()
  [[ "${ALLOW_TAG}" == "1" ]] && allow_tag_arg=(--allow-tag)
  python3 "${ROOT_DIR}/scripts/ops/assert_image_ref_digest.py" "${IMAGE_REF}" --context "dr_failback" "${allow_tag_arg[@]:-}" \
    || fail "IMAGE_REF must be digest-pinned; use --allow-tag for dev iteration only"
fi

for bin in aws kubectl python3 terraform; do
  command -v "${bin}" >/dev/null 2>&1 || fail "missing required command: ${bin}"
done

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER

if [[ -z "${RECEIPT_DIR}" ]]; then
  RECEIPT_DIR="/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/m19-dr-failback-$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "${RECEIPT_DIR}" || fail "cannot create receipt dir: ${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" || fail "receipt dir not writable: ${RECEIPT_DIR}"

TRANSITIONS_LOG="${RECEIPT_DIR}/state_transitions.log"
SUMMARY_JSON="${RECEIPT_DIR}/failback.summary.json"
PRIMARY_VALIDATE_LOG="${RECEIPT_DIR}/primary.validate.log"
PRIMARY_JOB_LOG="${RECEIPT_DIR}/primary.job.log"

PRIMARY_RUN_ID=""
PRIMARY_JOB_NAME=""
OVERALL_STATUS="running"
FAILED_STAGE=""
FAILED_REASON=""
START_TS="$(ts)"

transition() {
  local state="$1"
  local detail="${2:-}"
  local now
  now="$(ts)"
  printf '%s state=%s detail=%s\n' "${now}" "${state}" "${detail}" | tee -a "${TRANSITIONS_LOG}" >/dev/null
}

run_or_dry() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[DRY-RUN] $*" >> "${RECEIPT_DIR}/dry_run.commands.log"
    return 0
  fi
  "$@"
}

on_error() {
  local line="$1"
  local rc="$2"
  FAILED_REASON="line=${line} rc=${rc}"
  OVERALL_STATUS="failed"
  transition "error" "${FAILED_STAGE} ${FAILED_REASON}"
}
trap 'on_error "${LINENO}" "$?"' ERR

write_summary() {
  local end_ts
  end_ts="$(ts)"
  SUMMARY_PATH="${SUMMARY_JSON}" \
  SUMMARY_START="${START_TS}" \
  SUMMARY_END="${end_ts}" \
  SUMMARY_STATUS="${OVERALL_STATUS}" \
  SUMMARY_FAILED_STAGE="${FAILED_STAGE}" \
  SUMMARY_FAILED_REASON="${FAILED_REASON}" \
  SUMMARY_BUCKET="${BUCKET}" \
  SUMMARY_PREFIX="${PREFIX}" \
  SUMMARY_DR_RUN_ID="${DR_RUN_ID}" \
  SUMMARY_PRIMARY_RUN_ID="${PRIMARY_RUN_ID}" \
  SUMMARY_PRIMARY_JOB_NAME="${PRIMARY_JOB_NAME}" \
  SUMMARY_RECEIPT_DIR="${RECEIPT_DIR}" \
  SUMMARY_DRY_RUN="${DRY_RUN}" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "schema_version": 1,
    "start_timestamp_utc": os.environ["SUMMARY_START"],
    "end_timestamp_utc": os.environ["SUMMARY_END"],
    "status": os.environ["SUMMARY_STATUS"],
    "failed_stage": os.environ["SUMMARY_FAILED_STAGE"],
    "failed_reason": os.environ["SUMMARY_FAILED_REASON"],
    "bucket": os.environ["SUMMARY_BUCKET"],
    "prefix": os.environ["SUMMARY_PREFIX"],
    "dr_run_id": os.environ["SUMMARY_DR_RUN_ID"],
    "primary_run_id": os.environ["SUMMARY_PRIMARY_RUN_ID"],
    "primary_job_name": os.environ["SUMMARY_PRIMARY_JOB_NAME"],
    "dry_run": os.environ["SUMMARY_DRY_RUN"] == "true",
    "receipt_dir": os.environ["SUMMARY_RECEIPT_DIR"],
}
Path(os.environ["SUMMARY_PATH"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}
trap write_summary EXIT

confirm_intent_twice() {
  local required1="FAILBACK"
  local required2="CONFIRM-${DR_RUN_ID}"
  local v1="${CONFIRM1}"
  local v2="${CONFIRM2}"

  if [[ -z "${v1}" ]]; then
    read -r -p "Type '${required1}' to continue: " v1
  fi
  if [[ -z "${v2}" ]]; then
    read -r -p "Type '${required2}' to continue: " v2
  fi
  [[ "${v1}" == "${required1}" ]] || fail "first confirmation mismatch"
  [[ "${v2}" == "${required2}" ]] || fail "second confirmation mismatch"
}

assert_account_region() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    note "dry-run: skipping AWS account assertion"
    return 0
  fi
  local actual
  actual="$(aws sts get-caller-identity --query Account --output text)"
  [[ "${actual}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "account mismatch expected=${EXPECTED_ACCOUNT_ID} actual=${actual}"
}

cluster_reachable() {
  local kubeconfig="$1"
  local label="$2"
  run_or_dry kubectl --kubeconfig "${kubeconfig}" get nodes -o wide > "${RECEIPT_DIR}/${label}.nodes.txt"
  run_or_dry kubectl --kubeconfig "${kubeconfig}" -n "${NAMESPACE}" get ns "${NAMESPACE}" > "${RECEIPT_DIR}/${label}.namespace.txt"
}

check_dr_promoted() {
  local global_key="${PREFIX%/}/state/last_success.json"
  local provider_key="${PREFIX%/}/state/${PROVIDER}/${PROFILE}/last_success.json"
  local global_file="${RECEIPT_DIR}/pointer.global.json"
  local provider_file="${RECEIPT_DIR}/pointer.provider.json"

  run_or_dry aws s3 cp "s3://${BUCKET}/${global_key}" "${global_file}" >/dev/null
  run_or_dry aws s3 cp "s3://${BUCKET}/${provider_key}" "${provider_file}" >/dev/null

  if [[ "${DRY_RUN}" == "true" ]]; then
    return 0
  fi

  local global_run provider_run
  global_run="$(python3 - "${global_file}" <<'PY'
import json,sys
print(str(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("run_id","")).strip())
PY
)"
  provider_run="$(python3 - "${provider_file}" <<'PY'
import json,sys
print(str(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("run_id","")).strip())
PY
)"

  [[ "${global_run}" == "${DR_RUN_ID}" ]] || fail "DR not promoted: global pointer run_id=${global_run} expected=${DR_RUN_ID}"
  [[ "${provider_run}" == "${DR_RUN_ID}" ]] || fail "DR not promoted: provider pointer run_id=${provider_run} expected=${DR_RUN_ID}"
}

freeze_dr_scheduling() {
  local before="${RECEIPT_DIR}/dr.cronjobs.before.json"
  local after="${RECEIPT_DIR}/dr.cronjobs.after.json"
  run_or_dry kubectl --kubeconfig "${KUBECONFIG_DR}" -n "${NAMESPACE}" get cronjob -o json > "${before}"

  if [[ "${DRY_RUN}" != "true" ]]; then
    mapfile -t cronjobs < <(python3 - "${before}" <<'PY'
import json,sys
doc=json.load(open(sys.argv[1], "r", encoding="utf-8"))
for item in doc.get("items", []):
    name=item.get("metadata",{}).get("name","").strip()
    if name:
        print(name)
PY
)
    for cj in "${cronjobs[@]:-}"; do
      run_or_dry kubectl --kubeconfig "${KUBECONFIG_DR}" -n "${NAMESPACE}" patch cronjob "${cj}" --type merge -p '{"spec":{"suspend":true}}' >/dev/null
    done
  fi

  run_or_dry kubectl --kubeconfig "${KUBECONFIG_DR}" -n "${NAMESPACE}" get cronjob -o json > "${after}"
}

wait_no_inflight_dr_jobs() {
  local timeout_sec="${1:-300}"
  local slept=0

  while (( slept < timeout_sec )); do
    if [[ "${DRY_RUN}" == "true" ]]; then
      return 0
    fi

    local jobs_json pods_json
    jobs_json="${RECEIPT_DIR}/dr.jobs.active.json"
    pods_json="${RECEIPT_DIR}/dr.jobpods.active.json"
    kubectl --kubeconfig "${KUBECONFIG_DR}" -n "${NAMESPACE}" get jobs -o json > "${jobs_json}"
    kubectl --kubeconfig "${KUBECONFIG_DR}" -n "${NAMESPACE}" get pods -o json > "${pods_json}"

    local active_jobs active_job_pods
    active_jobs="$(python3 - "${jobs_json}" <<'PY'
import json,sys
doc=json.load(open(sys.argv[1], "r", encoding="utf-8"))
count=0
for item in doc.get("items", []):
    active=item.get("status", {}).get("active", 0) or 0
    count += int(active)
print(count)
PY
)"
    active_job_pods="$(python3 - "${pods_json}" <<'PY'
import json,sys
doc=json.load(open(sys.argv[1], "r", encoding="utf-8"))
count=0
for item in doc.get("items", []):
    labels=item.get("metadata", {}).get("labels", {}) or {}
    if "job-name" not in labels:
        continue
    phase=item.get("status", {}).get("phase", "")
    if phase not in ("Succeeded", "Failed"):
        count += 1
print(count)
PY
)"
    if [[ "${active_jobs}" == "0" && "${active_job_pods}" == "0" ]]; then
      return 0
    fi
    sleep 5
    slept=$((slept + 5))
  done

  fail "in-flight DR jobs did not drain within ${timeout_sec}s"
}

sync_artifacts_if_needed() {
  if [[ -z "${SYNC_SRC_PREFIX}" || -z "${SYNC_DST_PREFIX}" ]]; then
    note "sync step skipped (sync prefixes not provided)"
    return 0
  fi
  run_or_dry aws s3 sync "s3://${BUCKET}/${SYNC_SRC_PREFIX}" "s3://${BUCKET}/${SYNC_DST_PREFIX}" --exact-timestamps > "${RECEIPT_DIR}/sync.s3.log"
}

demote_dr() {
  local before="${RECEIPT_DIR}/dr.configmap.before.yaml"
  local after="${RECEIPT_DIR}/dr.configmap.after.yaml"
  if run_or_dry kubectl --kubeconfig "${KUBECONFIG_DR}" -n "${NAMESPACE}" get configmap jobintel-config -o yaml > "${before}"; then
    run_or_dry kubectl --kubeconfig "${KUBECONFIG_DR}" -n "${NAMESPACE}" patch configmap jobintel-config --type merge -p '{"data":{"PUBLISH_S3":"0","PUBLISH_S3_DRY_RUN":"1"}}' >/dev/null
    run_or_dry kubectl --kubeconfig "${KUBECONFIG_DR}" -n "${NAMESPACE}" get configmap jobintel-config -o yaml > "${after}"
  else
    note "jobintel-config configmap not found in DR namespace; skipping publish demotion patch"
  fi
}

restore_primary_if_required() {
  if [[ -z "${PRIMARY_RESTORE_BACKUP_URI}" ]]; then
    note "primary restore step skipped (no --primary-restore-backup-uri)"
    return 0
  fi
  run_or_dry "${ROOT_DIR}/scripts/ops/dr_restore.sh" --backup-uri "${PRIMARY_RESTORE_BACKUP_URI}" > "${RECEIPT_DIR}/primary.restore.log"
}

confirm_primary_healthy() {
  run_or_dry kubectl --kubeconfig "${KUBECONFIG_PRIMARY}" -n "${NAMESPACE}" get cronjob jobintel-daily > "${RECEIPT_DIR}/primary.cronjob.txt"
  run_or_dry kubectl --kubeconfig "${KUBECONFIG_PRIMARY}" -n "${NAMESPACE}" get deploy jobintel-dashboard > "${RECEIPT_DIR}/primary.dashboard.txt"
  run_or_dry kubectl --kubeconfig "${KUBECONFIG_PRIMARY}" -n "${NAMESPACE}" get pods -o wide > "${RECEIPT_DIR}/primary.pods.txt"

  if [[ "${DRY_RUN}" == "true" ]]; then
    PRIMARY_JOB_NAME="jobintel-dr-validate-dryrun"
    PRIMARY_RUN_ID="dryrun-primary-run-id"
    return 0
  fi

  HOME="${RECEIPT_DIR}/kube-home-primary" \
  KUBECONFIG="${KUBECONFIG_PRIMARY}" \
  RUN_JOB=1 \
  NAMESPACE="${NAMESPACE}" \
  IMAGE_REF="${IMAGE_REF}" \
  ALLOW_TAG="${ALLOW_TAG}" \
  "${ROOT_DIR}/scripts/ops/dr_validate.sh" > "${PRIMARY_VALIDATE_LOG}" 2>&1

  PRIMARY_JOB_NAME="$(sed -n 's/^DR_JOB_NAME=//p' "${PRIMARY_VALIDATE_LOG}" | tail -n 1 | tr -d '[:space:]' || true)"
  [[ -n "${PRIMARY_JOB_NAME}" ]] || fail "unable to parse primary validation job name"

  KUBECONFIG="${KUBECONFIG_PRIMARY}" kubectl -n "${NAMESPACE}" logs "job/${PRIMARY_JOB_NAME}" > "${PRIMARY_JOB_LOG}"
  PRIMARY_RUN_ID="$(sed -n 's/.*JOBINTEL_RUN_ID=//p' "${PRIMARY_JOB_LOG}" | head -n 1 | tr -d '[:space:]' || true)"
  [[ -n "${PRIMARY_RUN_ID}" ]] || fail "unable to parse JOBINTEL_RUN_ID from primary job logs"
}

verify_no_divergence() {
  [[ -n "${PRIMARY_RUN_ID}" ]] || fail "PRIMARY_RUN_ID is empty before divergence verification"

  if [[ "${DRY_RUN}" == "true" ]]; then
    note "dry-run: skipping live S3 divergence checks"
    return 0
  fi

  python3 "${ROOT_DIR}/scripts/verify_published_s3.py" \
    --bucket "${BUCKET}" \
    --run-id "${DR_RUN_ID}" \
    --prefix "${PREFIX}" > "${RECEIPT_DIR}/verify.dr_run.log"

  python3 "${ROOT_DIR}/scripts/verify_published_s3.py" \
    --bucket "${BUCKET}" \
    --run-id "${PRIMARY_RUN_ID}" \
    --prefix "${PREFIX}" \
    --verify-latest > "${RECEIPT_DIR}/verify.primary_run.log"

  local compare_root="${RECEIPT_DIR}/compare"
  local dr_dir="${compare_root}/dr/${DR_RUN_ID}"
  local primary_dir="${compare_root}/primary/${PRIMARY_RUN_ID}"
  mkdir -p "${dr_dir}" "${primary_dir}"

  aws s3 sync "s3://${BUCKET}/${PREFIX%/}/runs/${DR_RUN_ID}/" "${dr_dir}/"
  aws s3 sync "s3://${BUCKET}/${PREFIX%/}/runs/${PRIMARY_RUN_ID}/" "${primary_dir}/"

  python3 "${ROOT_DIR}/scripts/compare_run_artifacts.py" \
    "${dr_dir}" \
    "${primary_dir}" \
    --allow-run-id-drift \
    --repo-root "${ROOT_DIR}" > "${RECEIPT_DIR}/compare_run_artifacts.log"
}

teardown_dr() {
  if [[ "${TEARDOWN}" != "true" ]]; then
    note "teardown skipped (--teardown=false)"
    return 0
  fi

  run_or_dry env CONFIRM_DESTROY=1 "${ROOT_DIR}/scripts/ops/dr_teardown.sh" > "${RECEIPT_DIR}/dr_teardown.log"
  if [[ "${DRY_RUN}" == "true" ]]; then
    return 0
  fi

  aws ec2 describe-instances \
    --filters \
      "Name=tag:Name,Values=jobintel-dr-runner" \
      "Name=tag:Purpose,Values=jobintel-dr" \
      "Name=tag:ManagedBy,Values=terraform" \
      "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --output json > "${RECEIPT_DIR}/teardown.dr_runner_check.json"

  local remaining
  remaining="$(python3 - "${RECEIPT_DIR}/teardown.dr_runner_check.json" <<'PY'
import json,sys
doc=json.load(open(sys.argv[1], "r", encoding="utf-8"))
count=0
for r in doc.get("Reservations", []):
    count += len(r.get("Instances", []))
print(count)
PY
)"
  [[ "${remaining}" == "0" ]] || fail "DR teardown verification failed: remaining_instances=${remaining}"
}

main() {
  transition "start" "failback_begin"
  FAILED_STAGE="intent_confirmation"
  confirm_intent_twice

  FAILED_STAGE="account_region_preflight"
  assert_account_region
  transition "preflight_ok" "account_region_verified"

  FAILED_STAGE="primary_reachability"
  cluster_reachable "${KUBECONFIG_PRIMARY}" "primary"
  transition "primary_reachable" "kubectl_ok"

  FAILED_STAGE="dr_reachability"
  cluster_reachable "${KUBECONFIG_DR}" "dr"
  transition "dr_reachable" "kubectl_ok"

  FAILED_STAGE="dr_promoted_check"
  check_dr_promoted
  transition "dr_promoted_confirmed" "run_id=${DR_RUN_ID}"

  FAILED_STAGE="freeze_dr_scheduling"
  freeze_dr_scheduling
  transition "dr_frozen" "cronjobs_suspended"

  FAILED_STAGE="dr_inflight_drain"
  wait_no_inflight_dr_jobs 300
  transition "dr_quiesced" "no_inflight_jobs"

  FAILED_STAGE="sync_artifacts"
  sync_artifacts_if_needed
  transition "sync_complete" "artifacts_sync_checked"

  FAILED_STAGE="demote_dr"
  demote_dr
  transition "dr_demoted" "publish_disabled"

  FAILED_STAGE="restore_primary"
  restore_primary_if_required
  transition "primary_restore_checked" "restore_step_done"

  FAILED_STAGE="primary_health"
  confirm_primary_healthy
  transition "primary_healthy" "primary_run_id=${PRIMARY_RUN_ID}"

  FAILED_STAGE="divergence_check"
  verify_no_divergence
  transition "no_divergence_confirmed" "compare_ok"

  FAILED_STAGE="teardown_dr"
  teardown_dr
  transition "teardown_complete" "dr_destroyed_or_skipped"

  FAILED_STAGE=""
  FAILED_REASON=""
  OVERALL_STATUS="success"
  transition "complete" "failback_success"
  note "failback completed; receipt_dir=${RECEIPT_DIR}"
}

main "$@"
