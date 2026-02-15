# M17 API Boring Pack: Deterministic Smoke + Negative Coverage (2026-02-15)

## Summary

Strengthens M17 "API boring pack" with deterministic smoke scripts and negative test coverage for the dashboard API.

## What Was Added

### 1. Extended `scripts/dev/curl_dashboard_proof.sh`

- All core endpoints with HTTP status codes in output:
  - GET /version
  - GET /healthz
  - GET /v1/latest?candidate_id=local
  - GET /runs?candidate_id=local
  - GET /v1/runs/{run_id}/artifacts?candidate_id=local
- 404 example: GET /v1/runs/nonexistent-run-99999/artifacts with expected status 404
- Stable, human-readable output (status + JSON)

### 2. New `scripts/dev/dashboard_contract_smoke.sh`

- **Mode**: Assumes dashboard is already running (e.g. `make dashboard` in another terminal)
- Uses curl + jq to assert required keys:
  - `/version`: service, git_sha, schema_versions
  - `/v1/runs/{run_id}/artifacts`: run_id, candidate_id, artifacts (array); or 404 shape when no runs
- Exits non-zero if shape is wrong
- Does not print huge payloads (jq -e assertions only)

### 3. New Tests for GET /v1/runs/{run_id}/artifacts

- `test_dashboard_v1_artifact_index_rejects_invalid_run_id`: 400 for empty, slashes, oversized run_id
- `test_dashboard_v1_artifact_index_rejects_path_traversal_run_id`: 400 for `../etc/passwd`, `..`, etc.
- Existing: `test_dashboard_v1_artifact_index_bounded_no_huge_reads` (no artifact bodies in response)

## How to Run

```bash
# 1. Start dashboard (terminal 1)
make dashboard

# 2. Curl proof - human-readable endpoint tour (terminal 2)
./scripts/dev/curl_dashboard_proof.sh
./scripts/dev/curl_dashboard_proof.sh http://localhost:8000  # custom URL

# 3. Contract smoke - shape assertions, exits non-zero on failure
./scripts/dev/dashboard_contract_smoke.sh
./scripts/dev/dashboard_contract_smoke.sh http://localhost:8000  # custom URL

# 4. Unit tests (no live server)
make ci-fast
make gate
```

**Prerequisites**: `jq` for contract smoke (`brew install jq`).

## Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| /version and /artifacts response shape | dashboard_contract_smoke.sh + jq assertions |
| Invalid run_id rejected (400) | test_dashboard_v1_artifact_index_rejects_invalid_run_id |
| Path traversal in run_id rejected (400) | test_dashboard_v1_artifact_index_rejects_path_traversal_run_id |
| Bounded response (no artifact bodies) | test_dashboard_v1_artifact_index_bounded_no_huge_reads |
| 404 for unknown run | test_dashboard_v1_artifact_index_unknown_run_returns_404 |
| Deterministic proof output | curl_dashboard_proof.sh prints status + JSON |

## Validation Receipts

- `make format`
- `make lint`
- `make ci-fast`
- `make gate`
