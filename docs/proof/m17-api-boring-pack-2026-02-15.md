# Milestone 17 Proof - API Boring Pack (2026-02-15)

## Scope
Dashboard backend UI-ready without adding UI complexity. Add `/version` endpoint, document API contract, and provide simulated UI proof via curl.

## Endpoints Covered

| Endpoint | Status | Notes |
|----------|--------|-------|
| GET /version | **New** | service, git_sha, schema_versions (run_summary, run_health), optional build_timestamp |
| GET /healthz | Existing | Liveness |
| GET /v1/latest?candidate_id=... | Existing | Last success state |
| GET /runs?candidate_id=... | Existing | Run list |
| GET /runs/{run_id} | Existing | Run detail |
| GET /runs/{run_id}/artifact/{name} | Existing | Artifact fetch |
| GET /runs/{run_id}/semantic_summary/{profile} | Existing | Semantic summary |
| GET /v1/runs/{run_id} | Existing | Run receipt |
| GET /v1/artifacts/latest/{provider}/{profile} | Existing | Artifact index |

## How to Run the Curl Proof

1. Start the dashboard:
   ```bash
   make dashboard
   ```
   (Runs uvicorn on port 8000.)

2. In another terminal:
   ```bash
   ./scripts/dev/curl_dashboard_proof.sh
   ```
   Or with custom base URL:
   ```bash
   ./scripts/dev/curl_dashboard_proof.sh http://localhost:8000
   ```

## Test Commands Executed

```bash
# Unit tests (TestClient, no live server)
.venv/bin/python -m pytest tests/test_dashboard_app.py -v -k "version or healthz"

# Curl proof (requires dashboard running)
./scripts/dev/curl_dashboard_proof.sh
```

## Example /version Response

```json
{
  "service": "SignalCraft",
  "git_sha": "unknown",
  "schema_versions": {
    "run_summary": 1,
    "run_health": 1
  }
}
```

With env: `JOBINTEL_GIT_SHA=abc123`:
```json
{
  "service": "SignalCraft",
  "git_sha": "abc123",
  "schema_versions": {
    "run_summary": 1,
    "run_health": 1
  }
}
```

With env: `JOBINTEL_BUILD_TIMESTAMP=2026-02-15T12:00:00Z`:
```json
{
  "service": "SignalCraft",
  "git_sha": "unknown",
  "schema_versions": {...},
  "build_timestamp": "2026-02-15T12:00:00Z"
}
```

## What Did NOT Change

- Candidate-aware endpoints unchanged
- No authentication or multi-user UX
- No artifact storage layout changes
- Determinism unchanged
- Replay unchanged
- No snapshot baseline modification

## Validation Receipts

- `make format`
- `make lint`
- `make ci-fast`
- `make gate`
