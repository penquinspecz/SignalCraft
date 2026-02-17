#!/usr/bin/env bash
# Contract smoke: assert dashboard API response shapes via curl + jq.
# Mode: assumes dashboard is already running (e.g. make dashboard in another terminal).
# Usage: ./scripts/dev/dashboard_contract_smoke.sh [BASE_URL]

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

command -v jq >/dev/null 2>&1 || {
  echo "jq is required. Install via: brew install jq" >&2
  exit 2
}

curl -sS -o /dev/null -w "" --connect-timeout 2 "${BASE_URL}/version" 2>/dev/null || {
  echo "FAIL: Dashboard not reachable at $BASE_URL. Start with: make dashboard" >&2
  exit 1
}

_fail() {
  echo "FAIL: $*" >&2
  exit 1
}

_curl_json() {
  local url="$1"
  local code
  code=$(curl -sS -o /tmp/dash_smoke_body.json -w "%{http_code}" "$url")
  echo "$code"
}

echo "=== Dashboard contract smoke (base=$BASE_URL) ==="

# --- /version ---
code=$(_curl_json "${BASE_URL}/version")
if [[ "$code" != "200" ]]; then
  _fail "/version returned $code (expected 200)"
fi
if ! jq -e '.service and .git_sha and .schema_versions' /tmp/dash_smoke_body.json >/dev/null 2>&1; then
  _fail "/version missing required keys: service, git_sha, schema_versions"
fi
echo "  /version: OK (service, git_sha, schema_versions)"

# --- /v1/runs/{run_id}/artifacts ---
# Try to get a real run_id from /runs; if none, use nonexistent and expect 404
runs_json=$(curl -sS "${BASE_URL}/runs?candidate_id=local")
run_id=$(echo "$runs_json" | jq -r '.[0].run_id // empty')

if [[ -n "$run_id" ]]; then
  code=$(_curl_json "${BASE_URL}/v1/runs/${run_id}/artifacts?candidate_id=local")
  if [[ "$code" != "200" ]]; then
    _fail "/v1/runs/{run_id}/artifacts returned $code (expected 200 for run_id=$run_id)"
  fi
  if ! jq -e '.run_id and .candidate_id and (.artifacts | type == "array")' /tmp/dash_smoke_body.json >/dev/null 2>&1; then
    _fail "/v1/runs/{run_id}/artifacts missing required keys: run_id, candidate_id, artifacts (array)"
  fi
  echo "  /v1/runs/{run_id}/artifacts: OK (run_id, candidate_id, artifacts[])"
else
  code=$(_curl_json "${BASE_URL}/v1/runs/nonexistent-run-99999/artifacts?candidate_id=local")
  if [[ "$code" != "404" ]]; then
    _fail "/v1/runs/{run_id}/artifacts for nonexistent run returned $code (expected 404)"
  fi
  if ! jq -e '.detail' /tmp/dash_smoke_body.json >/dev/null 2>&1; then
    _fail "/v1/runs/{run_id}/artifacts 404 missing detail"
  fi
  echo "  /v1/runs/{run_id}/artifacts: OK (404 shape when run not found)"
fi

rm -f /tmp/dash_smoke_body.json
echo "=== All contract checks passed ==="
