#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/dr_approve.sh --execution-arn <arn> [--region us-east-1] [--expected-account-id 048622080012] [--approver <name>] [--ticket <id>] [--yes] [--dry-run]

Behavior:
  - Resolves pending Step Functions task token automatically (no copy/paste needed).
  - Shows approval summary before action.
  - Sends send-task-success when approved, send-task-failure when rejected.
EOF
}

EXECUTION_ARN=""
REGION=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
APPROVER="${APPROVER:-${USER:-unknown}}"
TICKET="${TICKET:-}"
AUTO_APPROVE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execution-arn)
      EXECUTION_ARN="${2:-}"
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
    --approver)
      APPROVER="${2:-}"
      shift 2
      ;;
    --ticket)
      TICKET="${2:-}"
      shift 2
      ;;
    --yes)
      AUTO_APPROVE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
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

[[ -n "${EXECUTION_ARN}" ]] || { usage; fail "--execution-arn is required"; }

command -v aws >/dev/null 2>&1 || fail "aws is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

read -r ARN_REGION ARN_ACCOUNT <<<"$(python3 - "${EXECUTION_ARN}" <<'PY'
import sys
arn = sys.argv[1]
parts = arn.split(":")
if len(parts) < 6 or parts[0] != "arn" or parts[2] != "states":
    raise SystemExit("invalid execution arn")
print(parts[3], parts[4])
PY
)"

[[ -n "${REGION}" ]] || REGION="${ARN_REGION}"
[[ "${ARN_ACCOUNT}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "Execution ARN account mismatch: expected=${EXPECTED_ACCOUNT_ID} arn_account=${ARN_ACCOUNT}"

export AWS_REGION="${REGION}"
export AWS_DEFAULT_REGION="${REGION}"
export AWS_PAGER=""

ACTUAL_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
[[ "${ACTUAL_ACCOUNT}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${ACTUAL_ACCOUNT}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

DESC_JSON="${TMP_DIR}/describe.json"
HIST_JSON="${TMP_DIR}/history.json"

aws stepfunctions describe-execution --execution-arn "${EXECUTION_ARN}" --output json > "${DESC_JSON}"
aws stepfunctions get-execution-history --execution-arn "${EXECUTION_ARN}" --reverse-order --max-results 200 --output json > "${HIST_JSON}"

SUMMARY_JSON="${TMP_DIR}/summary.json"
python3 - "${DESC_JSON}" "${HIST_JSON}" <<'PY' > "${SUMMARY_JSON}"
import json
import sys

desc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
hist = json.load(open(sys.argv[2], "r", encoding="utf-8"))
events = hist.get("events", [])

execution_arn = desc.get("executionArn", "")
execution_name = execution_arn.rsplit(":", 1)[-1] if execution_arn else ""
status = desc.get("status", "UNKNOWN")

raw_input = desc.get("input", "")
input_obj = {}
if isinstance(raw_input, str) and raw_input.strip():
    try:
        input_obj = json.loads(raw_input)
    except json.JSONDecodeError:
        input_obj = {}

receipt_bucket = str(input_obj.get("receipt_bucket", "")).strip()
receipt_prefix = str(input_obj.get("receipt_prefix", "")).strip("/")
expected_account_id = str(input_obj.get("expected_account_id", "")).strip()

receipt_base = ""
if receipt_bucket and receipt_prefix and execution_name:
    receipt_base = f"s3://{receipt_bucket}/{receipt_prefix}/{execution_name}"

task_token = ""
current_phase = ""
for ev in events:
    entered = ev.get("stateEnteredEventDetails")
    if isinstance(entered, dict) and entered.get("name"):
        current_phase = entered["name"]
        break

for ev in events:
    details = ev.get("taskScheduledEventDetails")
    if not isinstance(details, dict):
        continue
    params_text = details.get("parameters")
    if not isinstance(params_text, str) or "request_manual_approval" not in params_text:
        continue
    try:
        params = json.loads(params_text)
    except json.JSONDecodeError:
        continue
    payload = params.get("Payload", params.get("payload"))
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    token = str(payload.get("task_token", "")).strip()
    if token:
        task_token = token
        break

print(json.dumps({
    "execution_name": execution_name,
    "status": status,
    "current_phase": current_phase,
    "receipt_bucket": receipt_bucket,
    "receipt_prefix": receipt_prefix,
    "receipt_base": receipt_base,
    "expected_account_id": expected_account_id,
    "task_token": task_token,
}, sort_keys=True))
PY

read -r EXECUTION_NAME STATUS CURRENT_PHASE RECEIPT_BUCKET RECEIPT_PREFIX RECEIPT_BASE INPUT_EXPECTED_ACCOUNT TASK_TOKEN <<<"$(python3 - "${SUMMARY_JSON}" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
print(
    doc.get("execution_name", ""),
    doc.get("status", ""),
    doc.get("current_phase", ""),
    doc.get("receipt_bucket", ""),
    doc.get("receipt_prefix", ""),
    doc.get("receipt_base", ""),
    doc.get("expected_account_id", ""),
    doc.get("task_token", ""),
)
PY
)"

[[ "${STATUS}" == "RUNNING" ]] || fail "Execution is not RUNNING (status=${STATUS})"
if [[ -n "${INPUT_EXPECTED_ACCOUNT}" && "${INPUT_EXPECTED_ACCOUNT}" != "${EXPECTED_ACCOUNT_ID}" ]]; then
  fail "Execution input expected_account_id mismatch: expected=${EXPECTED_ACCOUNT_ID} input=${INPUT_EXPECTED_ACCOUNT}"
fi
[[ -n "${RECEIPT_BUCKET}" && -n "${RECEIPT_PREFIX}" && -n "${RECEIPT_BASE}" ]] || fail "Execution input missing receipt bucket/prefix"

MANUAL_URI="${RECEIPT_BASE}/request_manual_approval.json"
RESTORE_URI="${RECEIPT_BASE}/restore.json"

MANUAL_JSON="${TMP_DIR}/request_manual_approval.json"
if aws s3 cp "${MANUAL_URI}" "${MANUAL_JSON}" >/dev/null 2>&1; then
  read -r RECEIPT_TASK_TOKEN INSTANCE_ID BACKUP_URI <<<"$(python3 - "${MANUAL_JSON}" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
payload = doc.get("payload", {}) if isinstance(doc, dict) else {}
evt_input = payload.get("input", {}) if isinstance(payload, dict) else {}
summary = evt_input.get("summary", {}) if isinstance(evt_input, dict) else {}
print(
    str(evt_input.get("task_token", "")).strip(),
    str(summary.get("instance_id", "")).strip(),
    str(summary.get("backup_uri", "")).strip(),
)
PY
)"
  if [[ -z "${TASK_TOKEN}" && -n "${RECEIPT_TASK_TOKEN}" ]]; then
    TASK_TOKEN="${RECEIPT_TASK_TOKEN}"
  fi
else
  INSTANCE_ID=""
  BACKUP_URI=""
fi

[[ -n "${TASK_TOKEN}" ]] || fail "Unable to resolve pending task token from execution history or receipt ${MANUAL_URI}"

RESTORE_JSON="${TMP_DIR}/restore.json"
if aws s3 cp "${RESTORE_URI}" "${RESTORE_JSON}" >/dev/null 2>&1; then
  RESTORE_BACKUP_URI="$(python3 - "${RESTORE_JSON}" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
payload = doc.get("payload", {}) if isinstance(doc, dict) else {}
result = payload.get("result", {}) if isinstance(payload, dict) else {}
print(str(result.get("backup_uri", "")).strip())
PY
)"
  if [[ -z "${BACKUP_URI}" && -n "${RESTORE_BACKUP_URI}" ]]; then
    BACKUP_URI="${RESTORE_BACKUP_URI}"
  fi
fi

IMAGE_DIGEST="unknown"
RELEASE_METADATA_URI="unknown"
RELEASE_METADATA_SUMMARY="unknown"

if [[ -n "${BACKUP_URI}" ]]; then
  RELEASE_METADATA_URI="${BACKUP_URI%/}/metadata.json"
  META_JSON="${TMP_DIR}/metadata.json"
  if aws s3 cp "${RELEASE_METADATA_URI}" "${META_JSON}" >/dev/null 2>&1; then
    META_EXTRACT_JSON="${TMP_DIR}/metadata.extract.json"
    python3 - "${META_JSON}" <<'PY' > "${META_EXTRACT_JSON}"
import json, sys

doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))

def nested_get(obj, path):
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return cur if isinstance(cur, str) else ""

candidates = [
    ("image_digest",),
    ("release", "image_digest"),
    ("image", "digest"),
    ("container", "image_digest"),
]
digest = ""
for p in candidates:
    val = nested_get(doc, p).strip()
    if val:
        digest = val
        break

summary = {}
for key in ("run_id", "backup_id", "git_sha", "image_repo", "image_tag", "image_digest", "timestamp_utc"):
    if isinstance(doc, dict) and key in doc:
        summary[key] = doc[key]

release_obj = doc.get("release") if isinstance(doc, dict) else None
if isinstance(release_obj, dict):
    for key in ("git_sha", "image_repo", "image_tag", "image_digest", "supported_architectures", "build_timestamp_utc"):
        if key in release_obj:
            summary[f"release.{key}"] = release_obj[key]

text = json.dumps(summary, sort_keys=True) if summary else "metadata keys not recognized; inspect object"
print(json.dumps({
    "image_digest": digest or "unknown",
    "release_metadata_summary": text,
}, sort_keys=True))
PY
    IMAGE_DIGEST="$(python3 - "${META_EXTRACT_JSON}" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
print(doc.get("image_digest", "unknown"))
PY
)"
    RELEASE_METADATA_SUMMARY="$(python3 - "${META_EXTRACT_JSON}" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
print(doc.get("release_metadata_summary", "unknown"))
PY
)"
  fi
fi

echo "execution_arn=${EXECUTION_ARN}"
echo "status=${STATUS}"
echo "current_phase=${CURRENT_PHASE:-unknown}"
echo "instance_id=${INSTANCE_ID:-unknown}"
echo "image_digest=${IMAGE_DIGEST}"
echo "release_metadata=${RELEASE_METADATA_URI}"
echo "release_metadata_summary=${RELEASE_METADATA_SUMMARY}"
echo "restore_receipt=${RESTORE_URI}"

if [[ "${AUTO_APPROVE}" -eq 1 ]]; then
  DECISION="y"
else
  read -r -p "Approve DR manual promotion decision for this execution? [y/N] " DECISION
fi

if [[ "${DECISION}" =~ ^[Yy]$ ]]; then
  TASK_OUTPUT="$(python3 - "${APPROVER}" "${TICKET}" <<'PY'
import datetime as dt
import json
import sys
approver = sys.argv[1]
ticket = sys.argv[2]
payload = {
    "approved": True,
    "approver": approver,
    "ticket": ticket,
    "approved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
print(json.dumps(payload, separators=(",", ":")))
PY
)"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[DRY-RUN] Would send-task-success for execution ${EXECUTION_ARN}"
  else
    aws stepfunctions send-task-success \
      --task-token "${TASK_TOKEN}" \
      --task-output "${TASK_OUTPUT}" >/dev/null
    echo "[PASS] Approval sent (send-task-success)."
  fi
else
  read -r -p "Rejection reason: " REJECT_REASON
  [[ -n "${REJECT_REASON}" ]] || fail "Rejection reason is required"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[DRY-RUN] Would send-task-failure for execution ${EXECUTION_ARN} cause=${REJECT_REASON}"
  else
    aws stepfunctions send-task-failure \
      --task-token "${TASK_TOKEN}" \
      --error "ManualApprovalRejected" \
      --cause "${REJECT_REASON}" >/dev/null
    echo "[PASS] Rejection sent (send-task-failure)."
  fi
fi
