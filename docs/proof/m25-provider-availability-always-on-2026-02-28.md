# Milestone 25 Proof: Provider Availability Always-On (2026-02-28)

## Scope

Ensure `provider_availability_v1.json` is emitted on every terminal run path
as deterministic, schema-validated, UI-safe product truth.

## Implementation Notes

- Provider availability emission is now executed at the start of `_finalize(...)`
  via `_ensure_provider_availability_artifact(...)` in
  `src/ji_engine/pipeline/runner.py`.
- Finalization now attempts:
  1. primary writer
  2. fail-closed retry writer
  3. deterministic fallback writer
- Provider ordering remains deterministic (`sorted(provider_id)`).

## Artifact Examples

Canonical path for each run:
- `state/runs/<run_id>/artifacts/provider_availability_v1.json`

Covered terminal examples:
- Success path: emitted and schema-valid.
- Failure path (forced/provider-policy): emitted and schema-valid.
- Zero-provider selected/enabled path: emitted and schema-valid.

## Test Evidence

- `tests/test_run_health_artifact.py::test_run_health_written_on_success`
- `tests/test_run_health_artifact.py::test_provider_availability_on_forced_failure`
- `tests/test_run_health_artifact.py::test_provider_availability_written_on_scrape_only_early_exit`
- `tests/test_run_health_artifact.py::test_provider_availability_written_when_providers_all_filters_to_zero`
- `tests/test_run_health_artifact.py::test_provider_availability_records_partial_provider_failures`
- `tests/test_run_health_artifact.py::test_provider_availability_written_when_no_enabled_providers`
- `tests/test_run_health_artifact.py::test_provider_availability_written_on_provider_policy_failure`
- `tests/test_run_health_artifact.py::test_provider_availability_written_when_primary_and_retry_writers_fail`
