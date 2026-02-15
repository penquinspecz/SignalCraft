# M17: Artifact Index Endpoint (2026-02-14)

## Summary

Dashboard API "boring pack" readiness: stable artifact discovery via `GET /v1/runs/{run_id}/artifacts`.

## Endpoint

**GET /v1/runs/{run_id}/artifacts?candidate_id=...**

Returns a bounded artifact index for a run. No raw artifact bodies.

**Response shape** (200):
```json
{
  "run_id": "2026-01-22T00:00:00Z",
  "candidate_id": "local",
  "artifacts": [
    {
      "key": "run_summary.v1.json",
      "path": "run_summary.v1.json",
      "content_type": "application/json",
      "schema_version": 1,
      "size_bytes": 456
    },
    {
      "key": "openai_ranked_jobs.cs.json",
      "path": "openai_ranked_jobs.cs.json",
      "content_type": "application/json",
      "size_bytes": 2
    }
  ]
}
```

- `schema_version`: present for known schema artifacts (run_summary, run_health, provider_availability, run_report)
- `size_bytes`: present when file exists (via stat, no read)

**Status codes**:
- 200: Success
- 400: Invalid run_id or candidate_id
- 404: Run not found

## Client discovery flow

| Step | Endpoint | Purpose |
|------|----------|---------|
| 1 | GET /runs | List runs |
| 2 | GET /runs/{run_id} | Run detail (index + enrichment) |
| 3 | GET /v1/runs/{run_id}/artifacts | **Artifact index** (stable, bounded) |
| 4 | GET /runs/{run_id}/artifact/{name} | Download specific artifact |

## Fail-closed

- Artifacts from index.json only; no directory scan
- Path traversal rejected (absolute, `..`)
- Bounded: stat for size only; no payload read

## Verification

```bash
make format
make lint
make ci-fast
make gate
./scripts/dev/curl_dashboard_proof.sh
```

## Tests

- `test_dashboard_v1_artifact_index_shape_and_schema_versions`: response shape, schema_version
- `test_dashboard_v1_artifact_index_unknown_run_returns_404`: 404 for unknown run_id
- `test_dashboard_v1_artifact_index_bounded_no_huge_reads`: no artifact body in response

## Related

- [docs/DASHBOARD_API.md](../DASHBOARD_API.md) — endpoint documentation
- [src/ji_engine/dashboard/app.py](../../src/ji_engine/dashboard/app.py) — implementation
