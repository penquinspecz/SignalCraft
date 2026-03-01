# Job Timeline v1 Proof (2026-02-28)

## Scope
Deterministic, UI-safe job evolution timeline artifact with structured field diffs per `job_hash`.

## Artifact Paths
- `state/candidates/<candidate_id>/runs/<run_id>/artifacts/job_timeline_v1.json`
- `state/runs/<run_id>/artifacts/job_timeline_v1.json` (default-candidate compatibility)

## API Endpoint
- `GET /v1/jobs/{job_hash}/timeline?candidate_id=<candidate_id>`

## Test Evidence
- `tests/test_job_timeline_artifact_v1.py::test_job_timeline_artifact_deterministic`
- `tests/test_job_timeline_artifact_v1.py::test_job_timeline_artifact_schema_and_no_raw_jd_leak`
- `tests/test_job_timeline_artifact_v1.py::test_job_timeline_field_diff_correctness`
- `tests/test_dashboard_app.py::test_dashboard_v1_job_timeline_endpoint`
- `tests/test_dashboard_app.py::test_dashboard_v1_job_timeline_not_found`

## Example Payload Snippet
```json
{
  "job_timeline_schema_version": 1,
  "run_id": "2026-01-22T00:00:00Z",
  "candidate_id": "local",
  "jobs": [
    {
      "job_hash": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
      "provider_id": "openai",
      "canonical_url": "https://example.com/jobs/1",
      "changes": [
        {
          "changed_fields": [
            "compensation",
            "location",
            "seniority",
            "seniority_tokens",
            "skills",
            "title"
          ]
        }
      ]
    }
  ]
}
```
