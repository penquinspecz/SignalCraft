#!/usr/bin/env bash
# Force-fail demo: run pipeline with JOBINTEL_FORCE_FAIL_STAGE, print artifact paths.
# Safe offline (snapshot mode). Exit non-zero when forced failure occurs (expected).
#
# Usage: ./scripts/dev/force_fail_demo.sh [STAGE]
#   STAGE defaults to "scrape"
# Example: ./scripts/dev/force_fail_demo.sh classify

set -euo pipefail

STAGE="${1:-scrape}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PY="${PY:-}"
if [ -z "$PY" ] && [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PY="$REPO_ROOT/.venv/bin/python"
elif [ -z "$PY" ]; then
  PY="$(command -v python3 || command -v python)"
fi
DEMO_STATE="${JOBINTEL_FORCE_FAIL_DEMO_STATE:-/tmp/jobintel_force_fail_demo}"

mkdir -p "$DEMO_STATE"
export JOBINTEL_STATE_DIR="$DEMO_STATE"
export JOBINTEL_DATA_DIR="${JOBINTEL_DATA_DIR:-$REPO_ROOT/data}"
# Ensure snapshot exists for offline mode
if [ ! -f "$JOBINTEL_DATA_DIR/openai_snapshots/index.html" ]; then
  echo "[WARN] Snapshot not found at $JOBINTEL_DATA_DIR/openai_snapshots/index.html"
  echo "       Run with existing data/ or set JOBINTEL_DATA_DIR to a dir with openai_snapshots/"
fi
export JOBINTEL_FORCE_FAIL_STAGE="$STAGE"
export DISCORD_WEBHOOK_URL=""

echo "=== Force-fail demo (stage=$STAGE, offline) ==="
echo "STATE_DIR=$JOBINTEL_STATE_DIR"
echo ""

cd "$REPO_ROOT"
set +e
PYTHONPATH=src "$PY" scripts/run_daily.py --no_subprocess --profiles cs --offline --no_post
RC=$?
set -e

# Expected: non-zero exit on forced failure
if [ "$RC" -eq 0 ]; then
  echo ""
  echo "[WARN] Expected non-zero exit on forced failure; got 0. Check JOBINTEL_FORCE_FAIL_STAGE=$STAGE"
fi

# Find latest run dir (runs are created under state/runs/)
RUNS_DIR="$JOBINTEL_STATE_DIR/runs"
if [ -d "$RUNS_DIR" ]; then
  LATEST_RUN=$(find "$RUNS_DIR" -mindepth 1 -maxdepth 1 -type d | sort -r | head -1)
  if [ -n "$LATEST_RUN" ]; then
    echo ""
    echo "=== Artifact paths (latest run) ==="
    echo "run_dir=$LATEST_RUN"
    echo "run_health=$LATEST_RUN/run_health.v1.json"
    echo "run_summary=$LATEST_RUN/run_summary.v1.json"
    echo "run_report=$LATEST_RUN/run_report.json"
    echo "provider_availability=$LATEST_RUN/artifacts/provider_availability_v1.json"
    echo ""
    echo "Inspect via CLI:"
    RUN_ID=$(basename "$LATEST_RUN")
    echo "  PYTHONPATH=src $PY -m jobintel.cli runs show $RUN_ID --candidate-id local"
    echo "  PYTHONPATH=src $PY -m jobintel.cli runs artifacts $RUN_ID --candidate-id local"
    echo ""
    if [ -f "$LATEST_RUN/run_health.v1.json" ]; then
      echo "run_health.failed_stage=$("$PY" -c "import json,sys; d=json.load(sys.stdin); print(d.get('failed_stage',''))" < "$LATEST_RUN/run_health.v1.json")"
      echo "run_health.failure_codes=$("$PY" -c "import json,sys; d=json.load(sys.stdin); print(d.get('failure_codes',[]))" < "$LATEST_RUN/run_health.v1.json")"
    fi
  fi
fi

echo ""
echo "=== Done (exit_code=$RC, expected non-zero on forced failure) ==="
exit "$RC"
