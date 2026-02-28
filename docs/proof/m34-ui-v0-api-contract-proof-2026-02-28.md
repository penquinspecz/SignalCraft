# Milestone 34 Proof: UI v0 API Contract (2026-02-28)

## Scope

Validate API contract coverage for UI v0 read-only surface.

## Contract Additions

- `GET /ui` serves static UI page.
- `GET /v1/ui/latest` serves bounded aggregate payload:
  - latest run summary
  - top jobs
  - explanation artifact
  - provider availability
  - run health

Contract documentation updated in `docs/DASHBOARD_API.md`.

## Test Evidence

- `tests/test_dashboard_app.py::test_dashboard_ui_v0_static_page_served`
- `tests/test_dashboard_app.py::test_dashboard_v1_ui_latest_aggregate_payload_and_redaction`
- `tests/test_dashboard_app.py::test_dashboard_v1_ui_latest_bounded_reads_return_413`
- `tests/test_dashboard_app.py::test_dashboard_api_no_raw_jd_leakage[/v1/ui/latest-GET]`

## API Safety Assertions

- Aggregate endpoint enforces bounded reads via `JOBINTEL_DASHBOARD_MAX_JSON_BYTES` and returns HTTP 413 on overflow.
- Response is checked with fail-closed UI-safe assertion (`assert_no_forbidden_fields`).
- Replay-safe ranked-jobs payloads are redacted before top-job projection.

## Result

UI v0 surface is backend-driven, read-only, and contract-tested with no raw JD leakage.
