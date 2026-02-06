#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_URI=""

usage() {
  cat <<USAGE
Usage: $0 --backup-uri s3://<bucket>/<prefix>/backups/<backup_id>
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-uri)
      BACKUP_URI="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

[[ -n "${BACKUP_URI}" ]] || { usage; exit 2; }
command -v aws >/dev/null || { echo "aws cli is required" >&2; exit 2; }

contract_json="$(${ROOT_DIR}/scripts/ops/dr_contract.py --backup-uri "${BACKUP_URI}")"
bucket="$(echo "${contract_json}" | python -c 'import json,sys; print(json.load(sys.stdin)["bucket"])')"
keys="$(echo "${contract_json}" | python -c 'import json,sys; print("\n".join(json.load(sys.stdin)["required_keys"]))')"

missing=0
while IFS= read -r key; do
  [[ -n "${key}" ]] || continue
  if aws s3api head-object --bucket "${bucket}" --key "${key}" >/dev/null 2>&1; then
    echo "ok: s3://${bucket}/${key}"
  else
    echo "missing: s3://${bucket}/${key}" >&2
    missing=1
  fi
done <<< "${keys}"

if [[ "${missing}" -ne 0 ]]; then
  echo "backup contract check failed" >&2
  exit 3
fi

echo "backup contract validated"
echo "next: copy and restore backups on DR runner"
echo "  aws s3 cp ${BACKUP_URI}/state.tar.zst ."
echo "  aws s3 cp ${BACKUP_URI}/manifests.tar.zst ."
