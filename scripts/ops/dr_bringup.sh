#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT_DIR}/ops/dr/terraform"

command -v terraform >/dev/null || { echo "terraform is required" >&2; exit 2; }
command -v aws >/dev/null || { echo "aws cli is required" >&2; exit 2; }

APPLY="${APPLY:-0}"

cd "${TF_DIR}"
terraform init -input=false
terraform fmt -check
terraform validate
terraform plan -out=tfplan

if [[ "${APPLY}" == "1" ]]; then
  terraform apply -auto-approve tfplan
  terraform output
else
  echo "Plan generated at ${TF_DIR}/tfplan"
  echo "Set APPLY=1 to apply"
fi
