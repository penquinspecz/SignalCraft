#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

usage() {
  cat <<'USAGE'
Usage:
  scripts/control_plane/fetch_bundle.sh --bucket <bucket> --prefix <prefix> --dest-dir <dir>
  scripts/control_plane/fetch_bundle.sh --bundle-uri <uri-or-local-file> --bundle-sha256 <sha256> --dest-dir <dir>
USAGE
}

BUCKET=""
PREFIX=""
DEST_DIR=""
BUNDLE_URI=""
BUNDLE_SHA256=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="${2:-}"; shift 2 ;;
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --dest-dir) DEST_DIR="${2:-}"; shift 2 ;;
    --bundle-uri) BUNDLE_URI="${2:-}"; shift 2 ;;
    --bundle-sha256) BUNDLE_SHA256="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown arg: $1" ;;
  esac
done

[[ -n "${DEST_DIR}" ]] || fail "--dest-dir is required"
if [[ -z "${BUNDLE_URI}" ]]; then
  [[ -n "${BUCKET}" ]] || fail "--bucket is required when --bundle-uri is omitted"
  [[ -n "${PREFIX}" ]] || fail "--prefix is required when --bundle-uri is omitted"
fi

command -v python3 >/dev/null 2>&1 || fail "python3 is required"
needs_aws=0
if [[ -z "${BUNDLE_URI}" || "${BUNDLE_URI}" == s3://* ]]; then
  needs_aws=1
fi
if [[ "${needs_aws}" -eq 1 ]]; then
  command -v aws >/dev/null 2>&1 || fail "aws is required for S3 fetch"
  export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER
fi

mkdir -p "${DEST_DIR}" || fail "cannot create dest dir: ${DEST_DIR}"

if [[ "${needs_aws}" -eq 1 ]]; then
  ACTUAL_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
  [[ "${ACTUAL_ACCOUNT_ID}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${ACTUAL_ACCOUNT_ID}"
fi

POINTER_FILE="${DEST_DIR}/current.json"
if [[ -z "${BUNDLE_URI}" ]]; then
  CURRENT_URI="s3://${BUCKET}/${PREFIX%/}/control-plane/current.json"
  aws s3 cp "${CURRENT_URI}" "${POINTER_FILE}" >/dev/null
  read -r BUNDLE_URI BUNDLE_SHA256 <<<"$(python3 - "${POINTER_FILE}" <<'PY'
import json
import sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print(str(obj.get('bundle_uri', '')).strip(), str(obj.get('bundle_sha256', '')).strip())
PY
)"
  [[ -n "${BUNDLE_URI}" ]] || fail "current.json missing bundle_uri"
  [[ -n "${BUNDLE_SHA256}" ]] || fail "current.json missing bundle_sha256"
else
  [[ -n "${BUNDLE_SHA256}" ]] || fail "--bundle-sha256 is required when --bundle-uri is provided directly"
fi

BUNDLE_FILE="${DEST_DIR}/bundle.tar.gz"
if [[ "${BUNDLE_URI}" == s3://* ]]; then
  aws s3 cp "${BUNDLE_URI}" "${BUNDLE_FILE}" >/dev/null
else
  [[ -f "${BUNDLE_URI}" ]] || fail "bundle file not found: ${BUNDLE_URI}"
  cp "${BUNDLE_URI}" "${BUNDLE_FILE}"
fi

ACTUAL_BUNDLE_SHA256="$(python3 - "${BUNDLE_FILE}" <<'PY'
import hashlib
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
h = hashlib.sha256()
with p.open('rb') as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b''):
        h.update(chunk)
print(h.hexdigest())
PY
)"
[[ "${ACTUAL_BUNDLE_SHA256}" == "${BUNDLE_SHA256}" ]] || fail "bundle sha mismatch: expected=${BUNDLE_SHA256} actual=${ACTUAL_BUNDLE_SHA256}"

EXTRACT_DIR="${DEST_DIR}/bundle"
mkdir -p "${EXTRACT_DIR}"
tar -xzf "${BUNDLE_FILE}" -C "${EXTRACT_DIR}"
BUNDLE_DIR="${EXTRACT_DIR}/control-plane"
[[ -d "${BUNDLE_DIR}" ]] || fail "extracted bundle missing control-plane directory"
[[ -f "${BUNDLE_DIR}/manifest.json" ]] || fail "manifest.json missing in extracted bundle"

python3 - "${BUNDLE_DIR}" <<'PY'
import hashlib
import json
import pathlib
import sys

bundle = pathlib.Path(sys.argv[1])
manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
entries = manifest.get("files", [])
if not isinstance(entries, list) or not entries:
    raise SystemExit("manifest.files missing or empty")

expected = {}
for item in entries:
    if not isinstance(item, dict):
        raise SystemExit("manifest file entry is not object")
    rel = str(item.get("path", "")).strip()
    sha = str(item.get("sha256", "")).strip()
    if not rel or not sha:
        raise SystemExit("manifest file entry missing path/sha")
    expected[rel] = sha

actual_paths = []
for path in sorted(p for p in bundle.rglob("*") if p.is_file() and p.name != "manifest.json"):
    actual_paths.append(path.relative_to(bundle).as_posix())

if sorted(expected.keys()) != sorted(actual_paths):
    raise SystemExit("manifest file list does not match extracted file set")

for rel, sha in sorted(expected.items()):
    path = bundle / rel
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    if h != sha:
        raise SystemExit(f"file hash mismatch: {rel}")
PY

printf '%s\n' "${ACTUAL_BUNDLE_SHA256}" > "${DEST_DIR}/bundle.sha256"
cat > "${DEST_DIR}/fetch.summary.env" <<EOF_SUMMARY
BUNDLE_URI=${BUNDLE_URI}
BUNDLE_SHA256=${ACTUAL_BUNDLE_SHA256}
BUNDLE_FILE=${BUNDLE_FILE}
BUNDLE_DIR=${BUNDLE_DIR}
POINTER_FILE=${POINTER_FILE}
DEST_DIR=${DEST_DIR}
EOF_SUMMARY

note "control-plane bundle fetch complete"
echo "BUNDLE_URI=${BUNDLE_URI}"
echo "BUNDLE_SHA256=${ACTUAL_BUNDLE_SHA256}"
echo "BUNDLE_DIR=${BUNDLE_DIR}"
