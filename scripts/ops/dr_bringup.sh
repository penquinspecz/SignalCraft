#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT_DIR}/ops/dr/terraform"

command -v terraform >/dev/null 2>&1 || fail "terraform is required"
command -v aws >/dev/null 2>&1 || fail "aws cli is required"

APPLY="${APPLY:-0}"
TF_BACKEND_MODE="${TF_BACKEND_MODE:-remote}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
RECEIPT_DIR="${RECEIPT_DIR:-/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/m19-dr-bringup-$(date -u +%Y%m%dT%H%M%SZ)}"
export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER

export TF_IN_AUTOMATION="${TF_IN_AUTOMATION:-1}"
export TF_INPUT="${TF_INPUT:-0}"
[[ "${TF_IN_AUTOMATION}" == "1" ]] || fail "TF_IN_AUTOMATION must be 1 for dr_bringup"

mkdir -p "${RECEIPT_DIR}" || fail "cannot create receipt dir: ${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" || fail "receipt dir not writable: ${RECEIPT_DIR}"

actual_account="$(aws sts get-caller-identity --query Account --output text)"
[[ "${actual_account}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${actual_account}"

cat > "${RECEIPT_DIR}/dr_bringup.context.env" <<EOF
AWS_REGION=${AWS_REGION}
AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
EXPECTED_ACCOUNT_ID=${EXPECTED_ACCOUNT_ID}
ACTUAL_ACCOUNT_ID=${actual_account}
TF_IN_AUTOMATION=${TF_IN_AUTOMATION}
TF_INPUT=${TF_INPUT}
TF_BACKEND_MODE=${TF_BACKEND_MODE}
APPLY=${APPLY}
EOF

tf_init() {
  if [[ "${TF_BACKEND_MODE}" == "remote" ]]; then
    : "${TF_BACKEND_BUCKET:?TF_BACKEND_BUCKET is required when TF_BACKEND_MODE=remote}"
    : "${TF_BACKEND_KEY:?TF_BACKEND_KEY is required when TF_BACKEND_MODE=remote}"
    : "${TF_BACKEND_DYNAMODB_TABLE:?TF_BACKEND_DYNAMODB_TABLE is required when TF_BACKEND_MODE=remote}"
    terraform init -input=false \
      -backend-config="bucket=${TF_BACKEND_BUCKET}" \
      -backend-config="key=${TF_BACKEND_KEY}" \
      -backend-config="region=${AWS_REGION}" \
      -backend-config="dynamodb_table=${TF_BACKEND_DYNAMODB_TABLE}" \
      -backend-config="encrypt=true"
  else
    terraform init -input=false -backend=false
  fi
}

cd "${TF_DIR}"
tf_init 2>&1 | tee "${RECEIPT_DIR}/dr_bringup.tf_init.log"
terraform fmt -check 2>&1 | tee "${RECEIPT_DIR}/dr_bringup.tf_fmt.log"
terraform validate 2>&1 | tee "${RECEIPT_DIR}/dr_bringup.tf_validate.log"
terraform plan -input=false -out=tfplan 2>&1 | tee "${RECEIPT_DIR}/dr_bringup.tf_plan.log"

if [[ "${APPLY}" == "1" ]]; then
  terraform apply -input=false -auto-approve tfplan 2>&1 | tee "${RECEIPT_DIR}/dr_bringup.tf_apply.log"
  terraform output 2>&1 | tee "${RECEIPT_DIR}/dr_bringup.tf_output.txt"
  terraform output -json > "${RECEIPT_DIR}/dr_bringup.tf_output.json"
  note "bringup complete; receipt_dir=${RECEIPT_DIR}"
else
  echo "Plan generated at ${TF_DIR}/tfplan"
  echo "Set APPLY=1 to apply"
  note "bringup plan complete; receipt_dir=${RECEIPT_DIR}"
fi
