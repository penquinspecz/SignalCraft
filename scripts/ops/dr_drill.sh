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
  scripts/ops/dr_drill.sh --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
    [--image-ref <repo>@sha256:<digest>|<repo>:<tag>] \
    [--auto-promote true|false] \
    [--teardown true|false] \
    [--allow-promote-bypass true|false]

Defaults:
  --auto-promote false
  --teardown true
  --allow-promote-bypass false

Notes:
  - Promote executes only when --auto-promote=true and --allow-promote-bypass=true.
  - Teardown runs at the end when --teardown=true, even if earlier phases fail.
  - Required env: TF_VAR_vpc_id, TF_VAR_subnet_id.
  - When TF_BACKEND_MODE=remote (default), also set TF_BACKEND_BUCKET, TF_BACKEND_KEY, TF_BACKEND_DYNAMODB_TABLE.
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

BACKUP_URI=""
IMAGE_REF=""
AUTO_PROMOTE_RAW="false"
TEARDOWN_RAW="true"
ALLOW_PROMOTE_BYPASS_RAW="false"

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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -n "${BACKUP_URI}" ]] || { usage; fail "--backup-uri is required"; }
AUTO_PROMOTE="$(parse_bool "${AUTO_PROMOTE_RAW}")" || fail "Invalid --auto-promote: ${AUTO_PROMOTE_RAW}"
TEARDOWN="$(parse_bool "${TEARDOWN_RAW}")" || fail "Invalid --teardown: ${TEARDOWN_RAW}"
ALLOW_PROMOTE_BYPASS="$(parse_bool "${ALLOW_PROMOTE_BYPASS_RAW}")" || fail "Invalid --allow-promote-bypass: ${ALLOW_PROMOTE_BYPASS_RAW}"

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

[[ -n "${TF_VAR_vpc_id:-}" ]] || fail "TF_VAR_vpc_id is required"
[[ -n "${TF_VAR_subnet_id:-}" ]] || fail "TF_VAR_subnet_id is required"
if [[ "${TF_BACKEND_MODE}" == "remote" ]]; then
  [[ -n "${TF_BACKEND_BUCKET:-}" ]] || fail "TF_BACKEND_BUCKET is required when TF_BACKEND_MODE=remote"
  [[ -n "${TF_BACKEND_KEY:-}" ]] || fail "TF_BACKEND_KEY is required when TF_BACKEND_MODE=remote"
  [[ -n "${TF_BACKEND_DYNAMODB_TABLE:-}" ]] || fail "TF_BACKEND_DYNAMODB_TABLE is required when TF_BACKEND_MODE=remote"
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

python3 - "${BACKUP_URI}" "${RECEIPT_DIR}" "${START_TS}" "${GIT_SHA}" "${IMAGE_REF}" "${ACTUAL_ACCOUNT_ID}" "${AWS_REGION}" "${AUTO_PROMOTE}" "${TEARDOWN}" "${ALLOW_PROMOTE_BYPASS}" "${NAMESPACE}" "${MY_IP}" "${TF_BACKEND_MODE}" "${TF_VAR_vpc_id}" "${TF_VAR_subnet_id}" "${TF_VAR_allowed_cidr:-}" <<'PY'
import json
import pathlib
import sys

backup_uri, receipt_dir, start_ts, git_sha, image_ref, account_id, region, auto_promote, teardown, bypass, namespace, my_ip, backend_mode, vpc_id, subnet_id, allowed_cidr = sys.argv[1:]
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
}
pathlib.Path(receipt_dir, "drill.context.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

MAX_PHASE_ATTEMPTS=3
PHASE_DIR="${RECEIPT_DIR}/phases"
mkdir -p "${PHASE_DIR}"

OVERALL_STATUS="running"
FAILED_PHASE=""
FAILED_ERROR=""
INSTANCE_ID=""
PUBLIC_IP=""
SECURITY_GROUP_ID=""
KEY_NAME=""
DR_JOB_NAME=""
DR_RUN_ID=""
DR_KUBECONFIG_RAW="${RECEIPT_DIR}/k3s.raw.yaml"
DR_KUBECONFIG_PUBLIC="${RECEIPT_DIR}/k3s.public.yaml"
KUBE_HOME="${RECEIPT_DIR}/kube-home"
mkdir -p "${KUBE_HOME}"

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
  SUMMARY_DR_JOB_NAME="${DR_JOB_NAME}" \
  SUMMARY_DR_RUN_ID="${DR_RUN_ID}" \
  SUMMARY_KUBECONFIG_PUBLIC="${DR_KUBECONFIG_PUBLIC}" \
  SUMMARY_PHASE_DIR="${PHASE_DIR}" \
  SUMMARY_RECEIPT_DIR="${RECEIPT_DIR}" \
  SUMMARY_START_TS="${START_TS}" \
  SUMMARY_RUN_ID="${RUN_ID}" \
  SUMMARY_FILE="${RECEIPT_DIR}/drill.summary.json" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

phase_dir = Path(os.environ["SUMMARY_PHASE_DIR"])
phases = []
if phase_dir.exists():
    for p in sorted(phase_dir.glob("*.json")):
        try:
            phases.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            phases.append({"phase": p.stem, "status": "corrupt_receipt"})

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
    "dr_job_name": os.environ["SUMMARY_DR_JOB_NAME"],
    "dr_run_id": os.environ["SUMMARY_DR_RUN_ID"],
    "kubeconfig_public": os.environ["SUMMARY_KUBECONFIG_PUBLIC"],
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
  local ssm_params='{"commands":["set -euo pipefail","sudo test -s /etc/rancher/k3s/k3s.yaml","sudo cat /etc/rancher/k3s/k3s.yaml"]}'

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

for line in lines:
    m = re.match(r"^(\s*server:\s*)(\S+)\s*$", line)
    if not m:
        patched.append(line)
        continue
    prefix, server = m.group(1), m.group(2)
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
        patched.append(f"{prefix}https://{public_ip}:6443")
        updated = True
    else:
        patched.append(line)

out = "\n".join(patched) + "\n"
pathlib.Path(dst).write_text(out, encoding="utf-8")
print("patched" if updated else "unchanged")
PY
}

prepare_kubeconfig() {
  [[ -n "${INSTANCE_ID}" ]] || fail "INSTANCE_ID is empty"
  [[ -n "${PUBLIC_IP}" ]] || fail "PUBLIC_IP is empty"

  wait_for_ssm_online "${INSTANCE_ID}" 420
  fetch_k3s_kubeconfig_from_ssm "${INSTANCE_ID}"
  patch_kubeconfig_public_endpoint "${DR_KUBECONFIG_RAW}" "${DR_KUBECONFIG_PUBLIC}" "${PUBLIC_IP}" > "${RECEIPT_DIR}/kubeconfig.patch.result.txt"
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
  note "repair validate: refreshing kubeconfig via SSM"
  prepare_kubeconfig
  return 0
}

repair_teardown() {
  note "repair teardown: waiting before retry"
  sleep 5
  return 0
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
  read -r SECURITY_GROUP_ID KEY_NAME <<<"$(python3 - "${RECEIPT_DIR}/ec2.instance.json" <<'PY'
import json
import sys
d = json.load(open(sys.argv[1], "r", encoding="utf-8"))
inst = d["Reservations"][0]["Instances"][0]
sg = ""
if inst.get("SecurityGroups"):
    sg = inst["SecurityGroups"][0].get("GroupId", "")
print(sg, inst.get("KeyName", ""))
PY
)"

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
    --namespace "${NAMESPACE}"
}

phase_validate() {
  if [[ -n "${IMAGE_REF}" ]]; then
    CHECK_IMAGE_ONLY=1 CHECK_ARCH=arm64 IMAGE_REF="${IMAGE_REF}" "${ROOT_DIR}/scripts/ops/dr_validate.sh"
  fi

  HOME="${KUBE_HOME}" \
  KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" \
  RUN_JOB=1 \
  NAMESPACE="${NAMESPACE}" \
  IMAGE_REF="${IMAGE_REF}" \
  "${ROOT_DIR}/scripts/ops/dr_validate.sh"

  DR_JOB_NAME="$(sed -n 's/^DR_JOB_NAME=//p' "${CURRENT_PHASE_LOG}" | tail -n 1 || true)"
  if [[ -z "${DR_JOB_NAME}" ]]; then
    DR_JOB_NAME="$(HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" get jobs -o name \
      | sed 's#job.batch/##' \
      | rg '^jobintel-dr-validate-' \
      | tail -n 1 || true)"
  fi
  [[ -n "${DR_JOB_NAME}" ]] || fail "unable to resolve DR validate job name"

  HOME="${KUBE_HOME}" KUBECONFIG="${DR_KUBECONFIG_PUBLIC}" kubectl -n "${NAMESPACE}" logs "job/${DR_JOB_NAME}" > "${RECEIPT_DIR}/validate.job.log"
  DR_RUN_ID="$(sed -n 's/.*JOBINTEL_RUN_ID=//p' "${RECEIPT_DIR}/validate.job.log" | head -n 1 | tr -d '[:space:]' || true)"
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
  count="$(python3 - <<'PY' <<< "${out}"
import json
import sys
d = json.load(sys.stdin)
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
  local repaired=0
  local last_log=""
  local last_error=""

  note "phase=${phase} start"
  while (( attempts < MAX_PHASE_ATTEMPTS )); do
    attempts=$((attempts + 1))
    CURRENT_PHASE_LOG="${RECEIPT_DIR}/${phase}.attempt${attempts}.log"
    last_log="${CURRENT_PHASE_LOG}"

    set +e
    "${phase_fn}" > "${CURRENT_PHASE_LOG}" 2>&1
    local rc=$?
    set -e

    if [[ "${rc}" -eq 0 ]]; then
      write_phase_receipt "${phase}" "success" "${attempts}" "${repaired}" "${command_hint}" "${last_log}" "" "${started_at}" "$(ts)"
      note "phase=${phase} status=success attempts=${attempts}"
      return 0
    fi

    last_error="$(tail -n 60 "${CURRENT_PHASE_LOG}" || true)"
    echo "[FAIL] phase=${phase} attempt=${attempts}/${MAX_PHASE_ATTEMPTS} rc=${rc}" >&2
    echo "[FAIL] command=${command_hint}" >&2
    echo "[FAIL] stderr_tail:" >&2
    echo "${last_error}" >&2

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
  return 1
}

export TF_VAR_region="${AWS_REGION}"
if [[ -z "${TF_VAR_allowed_cidr:-}" && "${MY_IP}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  export TF_VAR_allowed_cidr="${MY_IP}/32"
fi

MAIN_FAILED=0

run_phase "bringup" phase_bringup repair_bringup "APPLY=1 scripts/ops/dr_bringup.sh" || MAIN_FAILED=1
if [[ "${MAIN_FAILED}" -eq 0 ]]; then
  run_phase "restore" phase_restore repair_restore "scripts/ops/dr_restore.sh --backup-uri <backup_uri>" || MAIN_FAILED=1
fi
if [[ "${MAIN_FAILED}" -eq 0 ]]; then
  run_phase "validate" phase_validate repair_validate "RUN_JOB=1 scripts/ops/dr_validate.sh" || MAIN_FAILED=1
fi
if [[ "${MAIN_FAILED}" -eq 0 ]]; then
  if [[ "${AUTO_PROMOTE}" == "true" ]]; then
    run_phase "promote" phase_promote "" "promote decision (manual bypass gated)" || MAIN_FAILED=1
  else
    write_skipped_phase "promote" "auto promote disabled"
  fi
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

OVERALL_STATUS="success"
exit 0
