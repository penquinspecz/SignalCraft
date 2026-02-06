#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT_DIR}/ops/dr/terraform"
CONFIRM_DESTROY="${CONFIRM_DESTROY:-0}"

command -v terraform >/dev/null || { echo "terraform is required" >&2; exit 2; }

cd "${TF_DIR}"
terraform init -input=false >/dev/null
terraform plan -destroy -out=tfplan-destroy

if [[ "${CONFIRM_DESTROY}" == "1" ]]; then
  terraform apply -auto-approve tfplan-destroy
else
  echo "Destroy plan generated at ${TF_DIR}/tfplan-destroy"
  echo "Set CONFIRM_DESTROY=1 to apply"
fi
