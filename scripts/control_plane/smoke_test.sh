#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

SRC_DIR="${WORK_DIR}/source"
mkdir -p "${SRC_DIR}"/{alerts,providers,scoring}
mkdir -p "${SRC_DIR}/candidates/local"

cat > "${SRC_DIR}/candidates/registry.json" <<'JSON'
{"schema_version":1,"candidates":[{"candidate_id":"local","profile_path":"candidates/local/candidate_profile.json"}]}
JSON
cat > "${SRC_DIR}/candidates/local/candidate_profile.json" <<'JSON'
{"schema_version":1,"basics":{"name":"Local"}}
JSON
cat > "${SRC_DIR}/alerts/alerts.json" <<'JSON'
{"schema_version":1,"rules":[]}
JSON
cat > "${SRC_DIR}/providers/providers.json" <<'JSON'
{"schema_version":1,"providers":[{"provider_id":"openai","enabled":true}]}
JSON
cat > "${SRC_DIR}/scoring/scoring.v1.json" <<'JSON'
{"schema_version":1,"version":"v1"}
JSON

PUBLISH_RECEIPT="${WORK_DIR}/publish"
mkdir -p "${PUBLISH_RECEIPT}"

"${ROOT_DIR}/scripts/control_plane/publish_bundle.sh" \
  --bucket dry-run-bucket \
  --prefix jobintel \
  --source-dir "${SRC_DIR}" \
  --dry-run \
  --receipt-dir "${PUBLISH_RECEIPT}" > "${WORK_DIR}/publish.out"

BUNDLE_FILE="$(sed -n 's/^BUNDLE_FILE=//p' "${PUBLISH_RECEIPT}/publish.summary.env")"
BUNDLE_SHA="$(sed -n 's/^BUNDLE_SHA256=//p' "${PUBLISH_RECEIPT}/publish.summary.env")"
[[ -f "${BUNDLE_FILE}" ]] || fail "bundle file missing from publish phase"
[[ -n "${BUNDLE_SHA}" ]] || fail "bundle sha missing from publish phase"

FETCH_DIR="${WORK_DIR}/fetch"
"${ROOT_DIR}/scripts/control_plane/fetch_bundle.sh" \
  --bundle-uri "${BUNDLE_FILE}" \
  --bundle-sha256 "${BUNDLE_SHA}" \
  --dest-dir "${FETCH_DIR}" > "${WORK_DIR}/fetch.out"

FETCH_BUNDLE_SHA="$(sed -n 's/^BUNDLE_SHA256=//p' "${FETCH_DIR}/fetch.summary.env")"
[[ "${FETCH_BUNDLE_SHA}" == "${BUNDLE_SHA}" ]] || fail "fetch sha mismatch"

APPLY_DIR="${WORK_DIR}/apply"
mkdir -p "${APPLY_DIR}"
"${ROOT_DIR}/scripts/control_plane/apply_bundle_k8s.sh" \
  --bundle-dir "${FETCH_DIR}/bundle/control-plane" \
  --namespace jobintel-smoke \
  --render-only \
  --output-yaml "${APPLY_DIR}/control-plane.configmaps.yaml" \
  --receipt-dir "${APPLY_DIR}" > "${WORK_DIR}/apply.out"

[[ -f "${APPLY_DIR}/control-plane.configmaps.yaml" ]] || fail "rendered yaml missing"
rg -q "name: jobintel-control-plane-candidates" "${APPLY_DIR}/control-plane.configmaps.yaml" || fail "candidate configmap missing"
rg -q "name: jobintel-control-plane-alerts" "${APPLY_DIR}/control-plane.configmaps.yaml" || fail "alerts configmap missing"
rg -q "name: jobintel-control-plane-providers" "${APPLY_DIR}/control-plane.configmaps.yaml" || fail "providers configmap missing"
rg -q "name: jobintel-control-plane-scoring" "${APPLY_DIR}/control-plane.configmaps.yaml" || fail "scoring configmap missing"

note "control-plane smoke test passed"
echo "WORK_DIR=${WORK_DIR}"
