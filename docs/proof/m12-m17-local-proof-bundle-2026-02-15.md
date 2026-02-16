# M12–M17 Local Proof Bundle (2026-02-15)

## Summary

Deterministic offline pipeline run + dashboard contract smoke + curl proof. Run artifacts are written to a temp dir and **are not committed**.

## Commands Run (copy/paste)

```bash
# 1. Offline pipeline (cronjob_simulate)
JOBINTEL_DATA_DIR=/tmp/jobintel_proof_bundle_xxx/data JOBINTEL_STATE_DIR=/tmp/jobintel_proof_bundle_xxx/state \
JOBINTEL_CRONJOB_RUN_ID=2026-01-01T00:00:00Z CAREERS_MODE=SNAPSHOT EMBED_PROVIDER=stub \
ENRICH_MAX_WORKERS=1 DISCORD_WEBHOOK_URL= \
PYTHONPATH=src .venv/bin/python scripts/cronjob_simulate.py

# 2. Start dashboard (separate terminal)
JOBINTEL_STATE_DIR=/tmp/jobintel_proof_bundle_xxx/state make dashboard

# 3. Contract smoke
./scripts/dev/dashboard_contract_smoke.sh http://localhost:8000

# 4. Curl proof
RUN_ID=2026-01-01T00:00:00Z ./scripts/dev/curl_dashboard_proof.sh http://localhost:8000 2026-01-01T00:00:00Z
```

## Artifacts Created (paths)

| Artifact | Path |
|----------|------|
| run_health | `$STATE_DIR/runs/20260101T000000Z/run_health.v1.json` |
| run_summary | `$STATE_DIR/runs/20260101T000000Z/run_summary.v1.json` |
| run_report | `$STATE_DIR/runs/20260101T000000Z/run_report.json` |
| provider_availability | `$STATE_DIR/runs/20260101T000000Z/artifacts/provider_availability_v1.json` (if present) |

## Dashboard Endpoints Checked

| Endpoint | Expected Status |
|----------|------------------|
| GET /version | 200 |
| GET /healthz | 200 |
| GET /v1/latest?candidate_id=local | 200 |
| GET /runs?candidate_id=local | 200 |
| GET /v1/runs/{run_id}/artifacts?candidate_id=local | 200 |

## Note

Run artifacts are written to a temp dir (e.g. `/tmp/jobintel_proof_bundle_$$`) and are **not committed** to git.

## How to Run (future releases)

```bash
# One command (requires: pip install -e '.[dashboard]', jq)
./scripts/dev/proof_bundle_local_run_and_dashboard.sh
```
