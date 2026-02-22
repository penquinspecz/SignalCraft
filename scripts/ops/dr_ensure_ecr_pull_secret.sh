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

AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION

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
  ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
  [[ -n "${ACCOUNT_ID}" ]] || fail "cannot resolve ECR registry: pass --image-ref or --ecr-registry, or ensure aws sts works"
  DOCKER_SERVER="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
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

# Create secret from ECR login (do not log password)
aws ecr get-login-password --region "${AWS_REGION}" | \
  "${KUBE_EXTRA[@]}" kubectl -n "${NAMESPACE}" create secret docker-registry "${SECRET_NAME}" \
  --docker-server="${DOCKER_SERVER}" \
  --docker-username=AWS \
  --docker-password-stdin \
  > "${RECEIPT_DIR}/create.log" 2>&1 || fail "kubectl create secret docker-registry failed; see ${RECEIPT_DIR}/create.log"

# Patch service account to use the secret (merge; idempotent)
"${KUBE_EXTRA[@]}" kubectl -n "${NAMESPACE}" patch serviceaccount "${SERVICE_ACCOUNT}" \
  --type=merge \
  -p="{\"imagePullSecrets\":[{\"name\":\"${SECRET_NAME}\"}]}" \
  > "${RECEIPT_DIR}/patch-sa.log" 2>&1 || true

note "ECR pull secret ${SECRET_NAME} created/refreshed in namespace ${NAMESPACE}"
echo "secret=${SECRET_NAME}" > "${RECEIPT_DIR}/result.env"
echo "server=${DOCKER_SERVER}" >> "${RECEIPT_DIR}/result.env"
