#!/usr/bin/env bash
# Create or refresh ECR pull secret for DR validate (k8s imagePullSecrets).
# Required for RUN_JOB=1 dr_validate when pulling from ECR.
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE=""
AWS_REGION=""
SECRET_NAME="ecr-pull"
SERVICE_ACCOUNT="jobintel"
RECEIPT_DIR=""
KUBECONFIG_PATH=""
IMAGE_REF=""
ECR_REGISTRY=""
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: scripts/ops/dr_ensure_ecr_pull_secret.sh \
  --namespace <ns> \
  --aws-region <region> \
  [--image-ref <repo>@sha256:<digest>] \
  [--secret-name ecr-pull] \
  [--service-account jobintel] \
  [--receipt-dir <path>] \
  [--kubeconfig <path>] \
  [--dry-run]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace) NAMESPACE="${2:-}"; shift 2 ;;
    --aws-region) AWS_REGION="${2:-}"; shift 2 ;;
    --image-ref) IMAGE_REF="${2:-}"; shift 2 ;;
    --ecr-registry) ECR_REGISTRY="${2:-}"; shift 2 ;;
    --secret-name) SECRET_NAME="${2:-}"; shift 2 ;;
    --service-account) SERVICE_ACCOUNT="${2:-}"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="${2:-}"; shift 2 ;;
    --kubeconfig) KUBECONFIG_PATH="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown arg: $1" ;;
  esac
done

[[ -n "${NAMESPACE}" ]] || { usage; fail "--namespace is required"; }
[[ -n "${AWS_REGION}" ]] || { usage; fail "--aws-region is required"; }
command -v aws >/dev/null 2>&1 || fail "aws is required"
command -v kubectl >/dev/null 2>&1 || fail "kubectl is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required for .dockerconfigjson generation"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER

actual_account="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
[[ -n "${actual_account}" ]] || fail "AWS credentials unavailable; ensure env creds or profile"
[[ "${actual_account}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${actual_account}"

# Resolve ECR registry (server) from image-ref or ecr-registry
if [[ -n "${ECR_REGISTRY}" ]]; then
  DOCKER_SERVER="${ECR_REGISTRY}"
elif [[ -n "${IMAGE_REF}" ]]; then
  # 048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:... -> 048622080012.dkr.ecr.us-east-1.amazonaws.com
  if [[ "${IMAGE_REF}" == *"@"* ]]; then
    DOCKER_SERVER="${IMAGE_REF%%@*}"
  else
    DOCKER_SERVER="${IMAGE_REF%%:*}"
  fi
  DOCKER_SERVER="${DOCKER_SERVER%%/*}"
else
  DOCKER_SERVER="${actual_account}.dkr.ecr.${AWS_REGION}.amazonaws.com"
fi

[[ -n "${DOCKER_SERVER}" ]] || fail "DOCKER_SERVER empty"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  note "dry-run: would create secret ${SECRET_NAME} in ${NAMESPACE} for server ${DOCKER_SERVER}"
  exit 0
fi

if [[ -z "${RECEIPT_DIR}" ]]; then
  RECEIPT_DIR="/tmp/dr-ecr-pull-$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" 2>/dev/null || true

KUBE_EXTRA=()
[[ -z "${KUBECONFIG_PATH}" ]] || KUBE_EXTRA=(--kubeconfig "${KUBECONFIG_PATH}")

# Delete existing secret so we can recreate with fresh token (ECR tokens expire)
"${KUBE_EXTRA[@]}" kubectl -n "${NAMESPACE}" delete secret "${SECRET_NAME}" --ignore-not-found=true > "${RECEIPT_DIR}/delete.log" 2>&1 || true

# Create secret using .dockerconfigjson (portable across kubectl versions; --docker-password-stdin not in older kubectl)
DOCKER_PASSWORD="$(aws ecr get-login-password --region "${AWS_REGION}")"
DOCKER_CONFIG_JSON="$(python3 - "${DOCKER_SERVER}" "${DOCKER_PASSWORD}" <<'PY'
import json, base64, sys
server, pw = sys.argv[1], sys.argv[2]
auth = base64.b64encode(f"AWS:{pw}".encode()).decode()
cfg = {"auths": {server: {"username": "AWS", "password": pw, "auth": auth}}}
print(json.dumps(cfg))
PY
)"
DOCKER_CONFIG_FILE="${RECEIPT_DIR}/.dockerconfigjson"
printf '%s' "${DOCKER_CONFIG_JSON}" > "${DOCKER_CONFIG_FILE}"
"${KUBE_EXTRA[@]}" kubectl -n "${NAMESPACE}" create secret generic "${SECRET_NAME}" \
  --type=kubernetes.io/dockerconfigjson \
  --from-file=.dockerconfigjson="${DOCKER_CONFIG_FILE}" \
  > "${RECEIPT_DIR}/create.log" 2>&1 || fail "kubectl create secret generic (dockerconfigjson) failed; see ${RECEIPT_DIR}/create.log"
rm -f "${DOCKER_CONFIG_FILE}"

# Patch service account to use the secret (merge; idempotent)
"${KUBE_EXTRA[@]}" kubectl -n "${NAMESPACE}" patch serviceaccount "${SERVICE_ACCOUNT}" \
  --type=merge \
  -p="{\"imagePullSecrets\":[{\"name\":\"${SECRET_NAME}\"}]}" \
  > "${RECEIPT_DIR}/patch-sa.log" 2>&1 || true

note "ECR pull secret ${SECRET_NAME} created/refreshed in namespace ${NAMESPACE}"
echo "secret=${SECRET_NAME}" > "${RECEIPT_DIR}/result.env"
echo "server=${DOCKER_SERVER}" >> "${RECEIPT_DIR}/result.env"
