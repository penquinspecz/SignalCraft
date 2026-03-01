# Milestone 34 Proof: UI v0 Recent Changes + Timeline API Contract (2026-02-28)

## Scope

Extend read-only UI v0 contract with job-change analytics surfaces.

## Contract Additions

- `GET /v1/ui/latest` now includes `recent_changes`:
  - bounded 30-day window metadata
  - notable change summaries (skills/seniority/location/compensation deltas)
- `GET /v1/jobs/{job_hash}/timeline` provides read-only, bounded timeline projection for a single job hash.

## Test Evidence

- `tests/test_dashboard_app.py::test_dashboard_v1_ui_latest_aggregate_payload_and_redaction`
- `tests/test_dashboard_app.py::test_dashboard_v1_job_timeline_endpoint_returns_projected_payload`
- `tests/test_dashboard_app.py::test_dashboard_v1_job_timeline_bounded_reads_return_413`
- `tests/test_dashboard_app.py::test_dashboard_api_no_raw_jd_leakage[/v1/jobs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/timeline-GET]`

## Safety Assertions

- Read-only behavior unchanged: endpoints are GET-only and return projected fields.
- No raw JD leakage: fail-closed checks + forbidden-field contract tests remain green.
- Bounded payload behavior: oversized timeline artifacts return HTTP 413.

## Result

UI v0 now surfaces longitudinal change intelligence via documented, bounded, read-only API contracts.
