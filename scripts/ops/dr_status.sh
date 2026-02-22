#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/dr_status.sh --execution-arn <arn> [--region us-east-1] [--expected-account-id 048622080012]
  scripts/ops/dr_status.sh --state-machine-arn <arn> [--region us-east-1] [--expected-account-id 048622080012]

Notes:
  - If --execution-arn is omitted, latest execution from --state-machine-arn is used.
  - Region and account are enforced before querying execution details.
EOF
}

EXECUTION_ARN=""
STATE_MACHINE_ARN=""
REGION=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execution-arn)
      EXECUTION_ARN="${2:-}"
      shift 2
      ;;
    --state-machine-arn)
      STATE_MACHINE_ARN="${2:-}"
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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

command -v aws >/dev/null 2>&1 || fail "aws is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

if [[ -z "${EXECUTION_ARN}" && -z "${STATE_MACHINE_ARN}" ]]; then
  usage
  fail "Provide --execution-arn or --state-machine-arn"
fi

if [[ -n "${EXECUTION_ARN}" ]]; then
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
fi

[[ -n "${REGION}" ]] || REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION="${REGION}"
export AWS_DEFAULT_REGION="${REGION}"
export AWS_PAGER=""

ACTUAL_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
[[ "${ACTUAL_ACCOUNT}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${ACTUAL_ACCOUNT}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

if [[ -z "${EXECUTION_ARN}" ]]; then
  LIST_JSON="${TMP_DIR}/list.json"
  aws stepfunctions list-executions \
    --state-machine-arn "${STATE_MACHINE_ARN}" \
    --max-results 20 \
    --output json > "${LIST_JSON}"

  EXECUTION_ARN="$(python3 - "${LIST_JSON}" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
items = doc.get("executions", [])
if not items:
    print("")
    raise SystemExit(0)
print(items[0].get("executionArn", ""))
PY
)"
  [[ -n "${EXECUTION_ARN}" ]] || fail "No executions found for state machine: ${STATE_MACHINE_ARN}"
fi

DESC_JSON="${TMP_DIR}/describe.json"
HIST_JSON="${TMP_DIR}/history.json"

aws stepfunctions describe-execution --execution-arn "${EXECUTION_ARN}" --output json > "${DESC_JSON}"
aws stepfunctions get-execution-history --execution-arn "${EXECUTION_ARN}" --reverse-order --max-results 200 --output json > "${HIST_JSON}"

python3 - "${DESC_JSON}" "${HIST_JSON}" <<'PY'
import json
import sys

desc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
hist = json.load(open(sys.argv[2], "r", encoding="utf-8"))
events = hist.get("events", [])

execution_arn = desc.get("executionArn", "")
status = desc.get("status", "UNKNOWN")
start = desc.get("startDate", "")
stop = desc.get("stopDate", "")

current_phase = ""
for ev in events:
    entered = ev.get("stateEnteredEventDetails")
    if isinstance(entered, dict) and entered.get("name"):
        current_phase = entered["name"]
        break

failure_reason = ""
for ev in events:
    details = None
    for k, v in ev.items():
        if k.endswith("EventDetails") and isinstance(v, dict):
            details = v
            if v.get("error") or v.get("cause"):
                break
    if not isinstance(details, dict):
        continue
    err = str(details.get("error", "")).strip()
    cause = str(details.get("cause", "")).strip()
    if err or cause:
        failure_reason = f"{err} {cause}".strip()
        break

receipt_base = ""
latest_receipt = ""

raw_input = desc.get("input", "")
input_obj = {}
if isinstance(raw_input, str) and raw_input.strip():
    try:
        input_obj = json.loads(raw_input)
    except json.JSONDecodeError:
        input_obj = {}

receipt_bucket = str(input_obj.get("receipt_bucket", "")).strip()
receipt_prefix = str(input_obj.get("receipt_prefix", "")).strip("/")
execution_name = execution_arn.rsplit(":", 1)[-1] if execution_arn else ""
if receipt_bucket and receipt_prefix and execution_name:
    receipt_base = f"s3://{receipt_bucket}/{receipt_prefix}/{execution_name}"

raw_output = desc.get("output", "")
if isinstance(raw_output, str) and raw_output.strip():
    try:
        output_obj = json.loads(raw_output)
    except json.JSONDecodeError:
        output_obj = {}
    phase_results = output_obj.get("phase_results", {}) if isinstance(output_obj, dict) else {}
    order = [
        "promote",
        "request_manual_approval",
        "notify",
        "validate",
        "restore",
        "resolve_runner",
        "bringup",
        "check_health",
    ]
    for phase in order:
        node = phase_results.get(phase)
        if isinstance(node, dict):
            uri = str(node.get("receipt_uri", "")).strip()
            if uri:
                latest_receipt = uri
                break

print(f"execution_arn={execution_arn}")
print(f"status={status}")
print(f"current_phase={current_phase or 'unknown'}")
print(f"failure_reason={failure_reason or 'none'}")
print(f"started_at={start}")
print(f"stopped_at={stop or 'running'}")
print(f"receipt_base={receipt_base or 'unknown'}")
print(f"latest_receipt={latest_receipt or 'unknown'}")
PY

