#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="${NAMESPACE:-jobintel}"
RUN_JOB="${RUN_JOB:-0}"
IMAGE_REF="${IMAGE_REF:-}"
CHECK_IMAGE_ONLY="${CHECK_IMAGE_ONLY:-0}"
CHECK_ARCH="${CHECK_ARCH:-arm64}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
RECEIPT_DIR="${RECEIPT_DIR:-/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/m19-dr-validate-$(date -u +%Y%m%dT%H%M%SZ)}"
export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER

command -v aws >/dev/null 2>&1 || fail "aws is required"
command -v kubectl >/dev/null 2>&1 || fail "kubectl is required"

mkdir -p "${RECEIPT_DIR}" || fail "cannot create receipt dir: ${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" || fail "receipt dir not writable: ${RECEIPT_DIR}"

actual_account="$(aws sts get-caller-identity --query Account --output text)"
[[ "${actual_account}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${actual_account}"

cat > "${RECEIPT_DIR}/dr_validate.context.env" <<EOF
AWS_REGION=${AWS_REGION}
AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
EXPECTED_ACCOUNT_ID=${EXPECTED_ACCOUNT_ID}
ACTUAL_ACCOUNT_ID=${actual_account}
NAMESPACE=${NAMESPACE}
RUN_JOB=${RUN_JOB}
CHECK_IMAGE_ONLY=${CHECK_IMAGE_ONLY}
CHECK_ARCH=${CHECK_ARCH}
IMAGE_REF=${IMAGE_REF}
EOF

if [[ "${CHECK_IMAGE_ONLY}" == "1" ]]; then
  [[ -n "${IMAGE_REF}" ]] || fail "IMAGE_REF is required when CHECK_IMAGE_ONLY=1"
  "${ROOT_DIR}/scripts/release/verify_ecr_image_arch.py" --image-ref "${IMAGE_REF}" --require-arch "${CHECK_ARCH}" \
    2>&1 | tee "${RECEIPT_DIR}/dr_validate.image_precheck.log"
  echo "dr validate image precheck completed" | tee "${RECEIPT_DIR}/dr_validate.result.txt"
  note "validate image check complete; receipt_dir=${RECEIPT_DIR}"
  exit 0
fi

kubectl get ns "${NAMESPACE}" >/dev/null
kubectl -n "${NAMESPACE}" get cronjob jobintel-daily 2>&1 | tee "${RECEIPT_DIR}/dr_validate.cronjob.txt"
kubectl -n "${NAMESPACE}" get deploy jobintel-dashboard 2>&1 | tee "${RECEIPT_DIR}/dr_validate.deploy.txt"
kubectl -n "${NAMESPACE}" get pods -o wide 2>&1 | tee "${RECEIPT_DIR}/dr_validate.pods.txt"

if [[ "${RUN_JOB}" == "1" ]]; then
  job="jobintel-dr-validate-$(date +%Y%m%d%H%M%S)"
  kubectl -n "${NAMESPACE}" create job --from=cronjob/jobintel-daily "${job}" 2>&1 | tee "${RECEIPT_DIR}/dr_validate.create_job.log"
  if [[ -n "${IMAGE_REF}" ]]; then
    "${ROOT_DIR}/scripts/release/verify_ecr_image_arch.py" --image-ref "${IMAGE_REF}" --require-arch "${CHECK_ARCH}" \
      2>&1 | tee "${RECEIPT_DIR}/dr_validate.image_override_precheck.log"
    kubectl -n "${NAMESPACE}" set image "job/${job}" "jobintel=${IMAGE_REF}" \
      2>&1 | tee "${RECEIPT_DIR}/dr_validate.set_image.log"
  fi
  kubectl -n "${NAMESPACE}" wait --for=condition=complete --timeout=45m "job/${job}" \
    2>&1 | tee "${RECEIPT_DIR}/dr_validate.wait.log"
  kubectl -n "${NAMESPACE}" logs "job/${job}" | tail -n 200 \
    | tee "${RECEIPT_DIR}/dr_validate.job_tail.log"
  echo "DR_JOB_NAME=${job}" | tee "${RECEIPT_DIR}/dr_validate.job_name.txt"
  echo "DR_JOB_NAME=${job}"
fi

echo "dr validate checks completed" | tee "${RECEIPT_DIR}/dr_validate.result.txt"
note "validate complete; receipt_dir=${RECEIPT_DIR}"
