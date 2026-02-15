#!/usr/bin/env bash
# Simulated UI proof: curl dashboard endpoints and print example responses.
# Prereq: make dashboard (or equivalent) running on BASE_URL.
# Usage: ./scripts/dev/curl_dashboard_proof.sh [BASE_URL]

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

echo "=== Dashboard API curl proof (base=$BASE_URL) ==="
echo ""

echo "--- GET /version ---"
curl -sS "${BASE_URL}/version" | python3 -m json.tool || echo "(failed)"
echo ""

echo "--- GET /healthz ---"
curl -sS "${BASE_URL}/healthz" | python3 -m json.tool || echo "(failed)"
echo ""

echo "--- GET /v1/latest?candidate_id=local ---"
curl -sS "${BASE_URL}/v1/latest?candidate_id=local" | python3 -m json.tool 2>/dev/null || echo "(404 or error - expected when no state)"
echo ""

echo "--- GET /runs?candidate_id=local ---"
curl -sS "${BASE_URL}/runs?candidate_id=local" | python3 -m json.tool 2>/dev/null || echo "(404 or error)"
echo ""

echo "--- GET /v1/runs/{run_id}/artifacts?candidate_id=local ---"
curl -sS "${BASE_URL}/v1/runs/2026-01-22T00:00:00Z/artifacts?candidate_id=local" | python3 -m json.tool 2>/dev/null || echo "(404 - expected when run not found)"
echo ""

echo "=== Done ==="
