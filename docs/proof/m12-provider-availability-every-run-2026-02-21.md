# M12 Proof: provider_availability on Every Run

Date: 2026-02-21

## Invariant
`provider_availability_v1.json` is emitted for every finalized run, including success, controlled failure, forced failure, and provider-policy failure paths.

Canonical artifact path:
- `<run_dir>/artifacts/provider_availability_v1.json`
- Implemented by `_provider_availability_path(run_id)` in `src/ji_engine/pipeline/runner.py`.

## Implementation Notes
- `_finalize(...)` now has a third-level fail-closed path:
  - primary writer: `_write_provider_availability_artifact(...)`
  - existing retry after provenance normalization
  - new deterministic last-resort writer: `_write_provider_availability_fallback_artifact(...)`
- Fallback payload remains schema-validated and UI-safe:
  - schema check via `validate_payload(..., _provider_availability_schema())`
  - forbidden-field check via `_redaction_guard_json(...)`
- Fail-closed taxonomy is explicit:
  - `reason_code = early_failure_unknown`
  - `unavailable_reason = fail_closed:unknown_due_to_early_failure`
- Provider list ordering is deterministic (`sorted(...)`).

## Test Evidence
Command:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_run_health_artifact.py
```

Result:
- `9 passed in 0.67s`

Coverage includes:
- `test_run_health_written_on_success`
- `test_run_health_written_on_controlled_failure`
- `test_provider_availability_on_forced_failure`
- `test_provider_availability_written_on_provider_policy_failure`
- `test_provider_availability_written_when_primary_and_retry_writers_fail` (new regression guard)

## Hygiene Validation
Commands:

```bash
make format
make lint
make ci-fast
make gate
```

Results:
- `make format`: `2 files reformatted, 407 files left unchanged`
- `make lint`: pass (`All checks passed!`)
- `make ci-fast`: `721 passed, 17 skipped`
- `make gate`: `721 passed, 17 skipped`; snapshot immutability PASS; replay smoke PASS (`checked=6 matched=6 mismatched=0 missing=0`)

## Determinism / Replay Safety
- No scoring logic changes.
- No snapshot selection changes.
- No schema format changes.
- Replay smoke and snapshot immutability remain green.
