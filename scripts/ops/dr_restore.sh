#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_URI=""
KUBECONFIG_PATH=""
NAMESPACE="jobintel"
CONTROL_PLANE_BUCKET=""
CONTROL_PLANE_PREFIX=""
CONTROL_PLANE_BUNDLE_URI=""
CONTROL_PLANE_BUNDLE_SHA256=""
SKIP_CONTROL_PLANE=0
IMAGE_REF=""
ALLOW_TAG="0"

usage() {
  cat <<USAGE
Usage: $0 --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> [--kubeconfig <path>] [--namespace <ns>] [--image-ref <ref>] [--control-plane-bucket <bucket>] [--control-plane-prefix <prefix>] [--control-plane-bundle-uri <uri>] [--control-plane-bundle-sha256 <sha>] [--skip-control-plane]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-uri)
      BACKUP_URI="${2:-}"
      shift 2
      ;;
    --image-ref)
      IMAGE_REF="${2:-}"
      shift 2
      ;;
    --kubeconfig)
      KUBECONFIG_PATH="${2:-}"
      shift 2
      ;;
    --namespace)
      NAMESPACE="${2:-}"
      shift 2
      ;;
    --control-plane-bucket)
      CONTROL_PLANE_BUCKET="${2:-}"
      shift 2
      ;;
    --control-plane-prefix)
      CONTROL_PLANE_PREFIX="${2:-}"
      shift 2
      ;;
    --control-plane-bundle-uri)
      CONTROL_PLANE_BUNDLE_URI="${2:-}"
      shift 2
      ;;
    --control-plane-bundle-sha256)
      CONTROL_PLANE_BUNDLE_SHA256="${2:-}"
      shift 2
      ;;
    --skip-control-plane)
      SKIP_CONTROL_PLANE=1
      shift
      ;;
    --allow-tag)
      ALLOW_TAG="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown arg: $1"
      ;;
  esac
done

[[ -n "${BACKUP_URI}" ]] || { usage; fail "--backup-uri is required"; }
command -v aws >/dev/null 2>&1 || fail "aws cli is required"

# M19A: When IMAGE_REF is provided, require digest pinning unless --allow-tag
if [[ -n "${IMAGE_REF}" ]]; then
  allow_tag_arg=()
  [[ "${ALLOW_TAG}" == "1" ]] && allow_tag_arg=(--allow-tag)
  python3 "${ROOT_DIR}/scripts/ops/assert_image_ref_digest.py" "${IMAGE_REF}" --context "dr_restore" "${allow_tag_arg[@]:-}" \
    || fail "IMAGE_REF must be digest-pinned; use --allow-tag for dev iteration only"
fi
PY_BIN="${PY_BIN:-python3}"
command -v "${PY_BIN}" >/dev/null 2>&1 || fail "${PY_BIN} is required"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
RECEIPT_DIR="${RECEIPT_DIR:-/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/m19-dr-restore-$(date -u +%Y%m%dT%H%M%SZ)}"
export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER

mkdir -p "${RECEIPT_DIR}" || fail "cannot create receipt dir: ${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" || fail "receipt dir not writable: ${RECEIPT_DIR}"

actual_account="$(aws sts get-caller-identity --query Account --output text)"
[[ "${actual_account}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${actual_account}"

cat > "${RECEIPT_DIR}/dr_restore.context.env" <<EOF
AWS_REGION=${AWS_REGION}
AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
EXPECTED_ACCOUNT_ID=${EXPECTED_ACCOUNT_ID}
ACTUAL_ACCOUNT_ID=${actual_account}
BACKUP_URI=${BACKUP_URI}
NAMESPACE=${NAMESPACE}
SKIP_CONTROL_PLANE=${SKIP_CONTROL_PLANE}
EOF

contract_json="$(${ROOT_DIR}/scripts/ops/dr_contract.py --backup-uri "${BACKUP_URI}")"
printf '%s\n' "${contract_json}" > "${RECEIPT_DIR}/dr_restore.contract.json"
bucket="$(echo "${contract_json}" | "${PY_BIN}" -c 'import json,sys; print(json.load(sys.stdin)["bucket"])')"
keys="$(echo "${contract_json}" | "${PY_BIN}" -c 'import json,sys; print("\n".join(json.load(sys.stdin)["required_keys"]))')"

missing=0
{
  while IFS= read -r key; do
    [[ -n "${key}" ]] || continue
    if aws s3api head-object --bucket "${bucket}" --key "${key}" >/dev/null 2>&1; then
      echo "ok: s3://${bucket}/${key}"
    else
      echo "missing: s3://${bucket}/${key}" >&2
      missing=1
    fi
  done <<< "${keys}"
} 2>&1 | tee "${RECEIPT_DIR}/dr_restore.head_object_checks.log"

if [[ "${missing}" -ne 0 ]]; then
  fail "backup contract check failed"
fi

echo "backup contract validated" | tee "${RECEIPT_DIR}/dr_restore.result.txt"
echo "next: copy and restore backups on DR runner" | tee -a "${RECEIPT_DIR}/dr_restore.result.txt"
echo "  aws s3 cp ${BACKUP_URI}/state.tar.zst ." | tee -a "${RECEIPT_DIR}/dr_restore.result.txt"
echo "  aws s3 cp ${BACKUP_URI}/manifests.tar.zst ." | tee -a "${RECEIPT_DIR}/dr_restore.result.txt"

if [[ "${SKIP_CONTROL_PLANE}" -eq 1 ]]; then
  note "control-plane continuity step skipped by flag"
  note "restore contract validation complete; receipt_dir=${RECEIPT_DIR}"
  exit 0
fi

if [[ -z "${KUBECONFIG_PATH}" ]]; then
  fail "--kubeconfig is required unless --skip-control-plane is set"
fi

read -r BACKUP_BUCKET BACKUP_PREFIX <<<"$(python3 - "${BACKUP_URI}" <<'PY'
import sys
uri = sys.argv[1]
if not uri.startswith("s3://"):
    raise SystemExit("backup uri must start with s3://")
payload = uri[len("s3://"):]
bucket, _, key = payload.partition("/")
key = key.strip("/")
if not bucket or not key:
    raise SystemExit("backup uri missing bucket or key prefix")
print(bucket, key)
PY
)"

if [[ -z "${CONTROL_PLANE_BUCKET}" ]]; then
  CONTROL_PLANE_BUCKET="${BACKUP_BUCKET}"
fi
if [[ -z "${CONTROL_PLANE_PREFIX}" && -z "${CONTROL_PLANE_BUNDLE_URI}" ]]; then
  CONTROL_PLANE_PREFIX="$(python3 - "${BACKUP_PREFIX}" <<'PY'
import sys
prefix = sys.argv[1].strip("/")
needle = "/backups/"
if needle in prefix:
    print(prefix.split(needle, 1)[0].strip("/"))
elif prefix.endswith("/backups"):
    print(prefix[:-len("/backups")].strip("/"))
else:
    raise SystemExit("cannot derive control-plane prefix from backup uri; pass --control-plane-prefix")
PY
)"
fi

CONTROL_PLANE_FETCH_DIR="${RECEIPT_DIR}/control-plane/fetch"
CONTROL_PLANE_APPLY_DIR="${RECEIPT_DIR}/control-plane/apply"
mkdir -p "${CONTROL_PLANE_FETCH_DIR}" "${CONTROL_PLANE_APPLY_DIR}"

if [[ -n "${CONTROL_PLANE_BUNDLE_URI}" ]]; then
  [[ -n "${CONTROL_PLANE_BUNDLE_SHA256}" ]] || fail "--control-plane-bundle-sha256 is required with --control-plane-bundle-uri"
  "${ROOT_DIR}/scripts/control_plane/fetch_bundle.sh" \
    --bundle-uri "${CONTROL_PLANE_BUNDLE_URI}" \
    --bundle-sha256 "${CONTROL_PLANE_BUNDLE_SHA256}" \
    --dest-dir "${CONTROL_PLANE_FETCH_DIR}" > "${RECEIPT_DIR}/dr_restore.control_plane.fetch.log"
else
  "${ROOT_DIR}/scripts/control_plane/fetch_bundle.sh" \
    --bucket "${CONTROL_PLANE_BUCKET}" \
    --prefix "${CONTROL_PLANE_PREFIX}" \
    --dest-dir "${CONTROL_PLANE_FETCH_DIR}" > "${RECEIPT_DIR}/dr_restore.control_plane.fetch.log"
fi

CONTROL_PLANE_BUNDLE_DIR="${CONTROL_PLANE_FETCH_DIR}/bundle/control-plane"
[[ -d "${CONTROL_PLANE_BUNDLE_DIR}" ]] || fail "control-plane bundle dir missing: ${CONTROL_PLANE_BUNDLE_DIR}"

"${ROOT_DIR}/scripts/control_plane/apply_bundle_k8s.sh" \
  --bundle-dir "${CONTROL_PLANE_BUNDLE_DIR}" \
  --namespace "${NAMESPACE}" \
  --kubeconfig "${KUBECONFIG_PATH}" \
  --receipt-dir "${CONTROL_PLANE_APPLY_DIR}" > "${RECEIPT_DIR}/dr_restore.control_plane.apply.log"

python3 - "${CONTROL_PLANE_FETCH_DIR}/fetch.summary.env" "${CONTROL_PLANE_APPLY_DIR}/apply.summary.json" "${RECEIPT_DIR}/dr_restore.control_plane.summary.json" <<'PY'
import json
import pathlib
import sys

fetch_env = pathlib.Path(sys.argv[1])
apply_json = pathlib.Path(sys.argv[2])
out = pathlib.Path(sys.argv[3])

fetch = {}
if fetch_env.exists():
    for line in fetch_env.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fetch[k] = v

apply = json.loads(apply_json.read_text(encoding="utf-8")) if apply_json.exists() else {}

payload = {
    "schema_version": 1,
    "bundle_uri": fetch.get("BUNDLE_URI", ""),
    "bundle_sha256": fetch.get("BUNDLE_SHA256", ""),
    "bundle_dir": fetch.get("BUNDLE_DIR", ""),
    "candidate_count": apply.get("candidate_count", 0),
    "alert_count": apply.get("alert_count", 0),
    "provider_count": apply.get("provider_count", 0),
    "scoring_count": apply.get("scoring_count", 0),
    "manifest_sha256": apply.get("manifest_sha256", ""),
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

note "restore contract validation complete; receipt_dir=${RECEIPT_DIR}"
