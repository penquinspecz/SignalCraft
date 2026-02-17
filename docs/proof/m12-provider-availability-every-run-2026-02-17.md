# M12 Proof: provider_availability on Every Run

Date: 2026-02-17

## Invariant
`provider_availability_v1.json` is emitted for every finalized run path (success and failure), with fail-closed metadata for ultra-early/incomplete provenance.

Canonical artifact path:
- `.../<run_id>/artifacts/provider_availability_v1.json`
- Implemented by `_provider_availability_path(run_id)` in `src/ji_engine/pipeline/runner.py`.

## Artifact Emission Audit
Code paths audited in `src/ji_engine/pipeline/runner.py`:
- `_write_provider_availability_artifact(...)` builds + schema-validates + writes artifact.
- `_finalize(...)` now always attempts provider availability write before run report/health/summary.
- Exception paths (`CalledProcessError`, `SystemExit`, generic `Exception`) all call `_finalize("error", ...)`.

Run modes audited:
- Success path: `_finalize("success")`
- Controlled failure: `SystemExit` / stage failure -> `_finalize("error", failed_stage=...)`
- Forced failure (`JOBINTEL_FORCE_FAIL_STAGE`): `record_stage(...)` raises `SystemExit` -> `_finalize("error", ...)`
- Provider policy block / network shield denial: provider policy failure branch -> `_finalize("error", failed_stage="provider_policy")`
- Provider disabled: included via providers config in artifact synthesis; reason code maps to `not_enabled`.

## Code Changes (Deterministic)
1. Fail-closed reason constants added:
- `EARLY_FAILURE_UNKNOWN_REASON_CODE = "early_failure_unknown"`
- `EARLY_FAILURE_UNKNOWN_UNAVAILABLE_REASON = "fail_closed:unknown_due_to_early_failure"`

2. `_provider_reason_code(...)` now accepts normalized availability and returns fail-closed reason code when unavailable reason provenance is absent.

3. `_write_provider_availability_artifact(...)` now injects explicit fail-closed `unavailable_reason` when provenance is incomplete.

4. `_finalize(...)` hardening:
- Removed early return on `scoring_model_metadata` failure so finalize still emits artifacts.
- Added fail-closed retry when primary provider-availability write fails.

## Scenario Evidence (Tests)
Targeted deterministic test command:

```bash
PYTHONPATH=src ./.venv/bin/python -m pytest -q \
  tests/test_run_health_artifact.py::test_run_health_written_on_success \
  tests/test_run_health_artifact.py::test_run_health_written_on_controlled_failure \
  tests/test_run_health_artifact.py::test_provider_availability_on_forced_failure \
  tests/test_run_health_artifact.py::test_provider_availability_written_on_provider_policy_failure
```

Result:
- `4 passed in 0.32s`

What each test asserts:
- Success: provider availability artifact exists and validates schema.
- Controlled failure: provider availability artifact exists and validates schema.
- Forced failure: provider availability artifact exists, `availability=unavailable`, fail-closed reason present.
- Provider policy failure: provider availability artifact exists, `reason_code=policy_denied`, policy/network-shield fields captured.

## Full Hygiene Commands
Executed:

```bash
make format
make lint
make ci-fast
make gate
```

Results:
- `make format`: clean
- `make lint`: clean
- `make ci-fast`: `659 passed, 16 skipped`
- `make gate`: `659 passed, 16 skipped`; snapshot immutability PASS; replay smoke PASS (`checked=6 matched=6 mismatched=0 missing=0`)

## Determinism / Replay Contract
No ROADMAP edits, no snapshot baseline changes, no network-dependent test additions.
Replay/snapshot checks remain green under `make gate`.
