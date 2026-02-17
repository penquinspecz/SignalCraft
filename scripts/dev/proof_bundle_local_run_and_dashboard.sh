#!/usr/bin/env bash
# Proof bundle: deterministic offline pipeline run + dashboard contract smoke + curl proof.
# Produces a proof doc in docs/proof/ with commands, artifact paths, and endpoint checks.
# Run artifacts are written to a temp dir (not committed).
#
# Usage: ./scripts/dev/proof_bundle_local_run_and_dashboard.sh
# Prereq: pip install -e '.[dashboard]', jq, curl

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PY="${PY:-}"
if [ -z "$PY" ] && [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PY="$REPO_ROOT/.venv/bin/python"
elif [ -z "$PY" ]; then
  PY="$(command -v python3 || command -v python)"
fi

PROOF_PORT="${PROOF_BUNDLE_PORT:-8001}"
BASE_URL="${PROOF_BUNDLE_BASE_URL:-http://localhost:$PROOF_PORT}"
RUN_ID="${JOBINTEL_CRONJOB_RUN_ID:-2026-01-01T00:00:00Z}"
PROOF_DIR="${PROOF_BUNDLE_DIR:-/tmp/jobintel_proof_bundle_$$}"
PROOF_DATE="${PROOF_BUNDLE_DATE:-$(date +%Y-%m-%d)}"
PROOF_DOC="$REPO_ROOT/docs/proof/m12-m17-local-proof-bundle-$PROOF_DATE.md"

DASH_PID=""

cleanup() {
  if [ -n "$DASH_PID" ] && kill -0 "$DASH_PID" 2>/dev/null; then
    kill "$DASH_PID" 2>/dev/null || true
    wait "$DASH_PID" 2>/dev/null || true
  fi
  # Optionally remove proof dir; leave for inspection by default
  # rm -rf "$PROOF_DIR"
}
trap cleanup EXIT

command -v jq >/dev/null 2>&1 || {
  echo "jq is required. Install via: brew install jq" >&2
  exit 2
}

# Dashboard deps (uvicorn, fastapi) required for proof
if ! "$PY" -c "import uvicorn, fastapi" 2>/dev/null; then
  echo "Dashboard deps missing. Install with: pip install -e '.[dashboard]'" >&2
  exit 2
fi

echo "=== Proof bundle: local run + dashboard contract ==="
echo "PROOF_DIR=$PROOF_DIR"
echo "RUN_ID=$RUN_ID"
echo ""

# 1) Create proof dirs
mkdir -p "$PROOF_DIR/data" "$PROOF_DIR/state"
export JOBINTEL_DATA_DIR="$PROOF_DIR/data"
export JOBINTEL_STATE_DIR="$PROOF_DIR/state"
export JOBINTEL_CRONJOB_RUN_ID="$RUN_ID"
export CAREERS_MODE=SNAPSHOT
export EMBED_PROVIDER=stub
export ENRICH_MAX_WORKERS=1
export DISCORD_WEBHOOK_URL=""

# 2) Run offline pipeline (cronjob_simulate seeds snapshots from repo)
cd "$REPO_ROOT"
echo "==> Running offline pipeline (cronjob_simulate)..."
PYTHONPATH=src "$PY" scripts/cronjob_simulate.py || {
  echo "FAIL: cronjob_simulate failed" >&2
  exit 1
}

# 3) Resolve run dir (sanitized: 2026-01-01T00:00:00Z -> 20260101T000000Z)
SANITIZED_RUN="$(echo "$RUN_ID" | tr -d ':-')"
RUN_DIR="$JOBINTEL_STATE_DIR/runs/$SANITIZED_RUN"
# Fallback: check candidates/local/runs (namespaced) or first dir in runs/
if [ ! -d "$RUN_DIR" ]; then
  RUN_DIR="$JOBINTEL_STATE_DIR/candidates/local/runs/$SANITIZED_RUN"
fi
if [ ! -d "$RUN_DIR" ]; then
  FIRST_RUN=$(ls -1d "$JOBINTEL_STATE_DIR/runs"/*/ 2>/dev/null | head -1)
  [ -n "$FIRST_RUN" ] && RUN_DIR="${FIRST_RUN%/}"
fi
if [ ! -d "$RUN_DIR" ]; then
  FIRST_RUN=$(ls -1d "$JOBINTEL_STATE_DIR/candidates/local/runs"/*/ 2>/dev/null | head -1)
  [ -n "$FIRST_RUN" ] && RUN_DIR="${FIRST_RUN%/}"
fi
if [ ! -d "$RUN_DIR" ]; then
  echo "FAIL: Run dir not found under $JOBINTEL_STATE_DIR" >&2
  exit 1
fi

echo "RUN_DIR=$RUN_DIR"
echo ""

# 4) Start dashboard in background
echo "==> Starting dashboard (background, port=$PROOF_PORT)..."
PYTHONPATH=src JOBINTEL_STATE_DIR="$JOBINTEL_STATE_DIR" "$PY" -m uvicorn ji_engine.dashboard.app:app --port "$PROOF_PORT" &
DASH_PID=$!

# 5) Wait for dashboard to be reachable
for i in $(seq 1 15); do
  if curl -sS -o /dev/null -w "" --connect-timeout 2 "$BASE_URL/version" 2>/dev/null; then
    break
  fi
  [ "$i" -eq 15 ] && {
    echo "FAIL: Dashboard not reachable at $BASE_URL after 15 attempts" >&2
    exit 1
  }
  sleep 1
done
echo "Dashboard ready."
echo ""

# 6) Run contract smoke
echo "==> Running dashboard_contract_smoke.sh..."
"$SCRIPT_DIR/dashboard_contract_smoke.sh" "$BASE_URL" || {
  echo "FAIL: dashboard_contract_smoke failed" >&2
  exit 1
}
echo ""

# 7) Run curl proof and capture output
CURL_PROOF_FILE="$PROOF_DIR/curl_proof_output.txt"
echo "==> Running curl_dashboard_proof.sh..."
RUN_ID="$RUN_ID" "$SCRIPT_DIR/curl_dashboard_proof.sh" "$BASE_URL" "$RUN_ID" | tee "$CURL_PROOF_FILE" || {
  echo "FAIL: curl_dashboard_proof failed" >&2
  exit 1
}
echo ""

# 8) Print primary artifact paths
echo "==> Primary artifacts for run_id=$RUN_ID"
for f in run_health.v1.json run_summary.v1.json run_report.json; do
  p="$RUN_DIR/$f"
  [ -f "$p" ] && echo "  $p"
done
for p in "$RUN_DIR"/artifacts/provider_availability_v1.json; do
  [ -f "$p" ] && echo "  $p"
done
echo ""

# 9) Write proof doc
mkdir -p "$(dirname "$PROOF_DOC")"
cat > "$PROOF_DOC" << PROOFEOF
# M12–M17 Local Proof Bundle ($PROOF_DATE)

## Summary

Deterministic offline pipeline run + dashboard contract smoke + curl proof. Run artifacts are written to a temp dir and **are not committed**.

## Commands Run (copy/paste)

\`\`\`bash
# 1. Offline pipeline (cronjob_simulate)
JOBINTEL_DATA_DIR=$PROOF_DIR/data JOBINTEL_STATE_DIR=$PROOF_DIR/state \\
JOBINTEL_CRONJOB_RUN_ID=$RUN_ID CAREERS_MODE=SNAPSHOT EMBED_PROVIDER=stub \\
ENRICH_MAX_WORKERS=1 DISCORD_WEBHOOK_URL= \\
PYTHONPATH=src .venv/bin/python scripts/cronjob_simulate.py

# 2. Start dashboard (separate terminal)
JOBINTEL_STATE_DIR=$PROOF_DIR/state make dashboard

# 3. Contract smoke
./scripts/dev/dashboard_contract_smoke.sh $BASE_URL

# 4. Curl proof
RUN_ID=$RUN_ID ./scripts/dev/curl_dashboard_proof.sh $BASE_URL $RUN_ID
\`\`\`

## Artifacts Created (paths)

| Artifact | Path |
|----------|------|
| run_health | \`$RUN_DIR/run_health.v1.json\` |
| run_summary | \`$RUN_DIR/run_summary.v1.json\` |
| run_report | \`$RUN_DIR/run_report.json\` |
| provider_availability | \`$RUN_DIR/artifacts/provider_availability_v1.json\` (if present) |

## Dashboard Endpoints Checked

| Endpoint | Expected Status |
|----------|------------------|
| GET /version | 200 |
| GET /healthz | 200 |
| GET /v1/latest?candidate_id=local | 200 |
| GET /runs?candidate_id=local | 200 |
| GET /v1/runs/{run_id}/artifacts?candidate_id=local | 200 |

## Note

Run artifacts are written to \`$PROOF_DIR\` and are **not committed** to git.

## How to Run (future releases)

\`\`\`bash
# One command (requires: pip install -e '.[dashboard]', jq)
./scripts/dev/proof_bundle_local_run_and_dashboard.sh
\`\`\`
PROOFEOF

echo "==> Proof doc written: $PROOF_DOC"
echo ""
echo "=== Proof bundle complete ==="
