#!/usr/bin/env bash
# Simulated UI proof: curl dashboard endpoints and print example responses.
# Prereq: make dashboard (or equivalent) running on BASE_URL.
# Usage: ./scripts/dev/curl_dashboard_proof.sh [BASE_URL]

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

_show() {
  local url="$1"
  local label="${2:-}"
  local out
  out=$(curl -sS -w "\n%{http_code}" "$url")
  local body="${out%$'\n'*}"
  local code="${out##*$'\n'}"
  echo "status: $code${label:+ $label}"
  echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
  echo ""
}

echo "=== Dashboard API curl proof (base=$BASE_URL) ==="
echo ""

echo "--- GET /version ---"
_show "${BASE_URL}/version"

echo "--- GET /healthz ---"
_show "${BASE_URL}/healthz"

echo "--- GET /v1/latest?candidate_id=local ---"
_show "${BASE_URL}/v1/latest?candidate_id=local"

echo "--- GET /runs?candidate_id=local ---"
_show "${BASE_URL}/runs?candidate_id=local"

echo "--- GET /v1/runs/{run_id}/artifacts?candidate_id=local ---"
_show "${BASE_URL}/v1/runs/2026-01-22T00:00:00Z/artifacts?candidate_id=local"

echo "--- GET /v1/runs/{run_id}/artifacts (404 example: nonexistent run) ---"
_show "${BASE_URL}/v1/runs/nonexistent-run-99999/artifacts?candidate_id=local" "(expected: 404)"

echo "=== Done ==="
