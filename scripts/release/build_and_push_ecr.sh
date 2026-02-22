#!/usr/bin/env bash
set -euo pipefail

# Deterministic multi-arch ECR publisher for release images.
# Produces one tag (git SHA by default) with both amd64+arm64 manifests.

AWS_REGION="${AWS_REGION:-${JOBINTEL_AWS_REGION:-us-east-1}}"
ECR_REPO="${ECR_REPO:-jobintel}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
IMAGE_REPO_OVERRIDE="${IMAGE_REPO_OVERRIDE:-}"
RELEASE_METADATA_PATH="${RELEASE_METADATA_PATH:-}"
BUILD_TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

command -v aws >/dev/null 2>&1 || { echo "aws cli is required" >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 2; }

if [[ -z "${IMAGE_TAG}" ]]; then
  IMAGE_TAG="$(git rev-parse HEAD)"
fi

if [[ -z "${AWS_ACCOUNT_ID}" ]]; then
  AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
fi

if [[ -n "${IMAGE_REPO_OVERRIDE}" ]]; then
  IMAGE_REPO="${IMAGE_REPO_OVERRIDE}"
else
  IMAGE_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
fi
IMAGE_REF_TAGGED="${IMAGE_REPO}:${IMAGE_TAG}"

if ! aws ecr describe-repositories --repository-names "${ECR_REPO}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  aws ecr create-repository --repository-name "${ECR_REPO}" --region "${AWS_REGION}" >/dev/null
fi

aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com" >/dev/null

# Ensure buildx builder exists and is active.
BUILDER_NAME="signalcraft-multiarch"
if docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
  docker buildx use "${BUILDER_NAME}" >/dev/null
else
  docker buildx create --name "${BUILDER_NAME}" --driver docker-container --use >/dev/null
fi
docker buildx inspect --bootstrap >/dev/null

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag "${IMAGE_REF_TAGGED}" \
  --push \
  .

IMAGE_DIGEST="$(aws ecr describe-images \
  --region "${AWS_REGION}" \
  --repository-name "${ECR_REPO}" \
  --image-ids imageTag="${IMAGE_TAG}" \
  --query 'imageDetails[0].imageDigest' \
  --output text)"

if [[ "${IMAGE_DIGEST}" == "None" || -z "${IMAGE_DIGEST}" ]]; then
  echo "failed to resolve pushed image digest for ${IMAGE_REF_TAGGED}" >&2
  exit 1
fi

if [[ -z "${RELEASE_METADATA_PATH}" ]]; then
  RELEASE_METADATA_PATH="ops/proof/releases/release-${IMAGE_TAG}.json"
fi
mkdir -p "$(dirname "${RELEASE_METADATA_PATH}")"

python3 scripts/release/write_release_metadata.py \
  --image-repo "${IMAGE_REPO}" \
  --image-tag "${IMAGE_TAG}" \
  --image-digest "${IMAGE_DIGEST}" \
  --aws-region "${AWS_REGION}" \
  --git-sha "$(git rev-parse HEAD)" \
  --build-timestamp "${BUILD_TIMESTAMP_UTC}" \
  --output "${RELEASE_METADATA_PATH}"

printf 'IMAGE_REPO=%s\n' "${IMAGE_REPO}"
printf 'IMAGE_TAG=%s\n' "${IMAGE_TAG}"
printf 'IMAGE_DIGEST=%s\n' "${IMAGE_DIGEST}"
printf 'IMAGE_REF=%s@%s\n' "${IMAGE_REPO}" "${IMAGE_DIGEST}"
printf 'RELEASE_METADATA=%s\n' "${RELEASE_METADATA_PATH}"
