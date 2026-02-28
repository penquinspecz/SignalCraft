# M12 Proof: provider_availability emitted on zero-provider terminal path

Date (UTC): 2026-02-28T05:11:38Z
Main SHA inspected: `af1040cb8e730bd8674e3e1a894f0acf9da4e8e4`

## Root cause
`main()` resolved providers before entering the guarded execution path that calls `_finalize(...)`.
When provider selection failed with `No enabled providers configured`, the process exited with `SystemExit(2)` before finalization, so terminal artifacts (including `artifacts/provider_availability_v1.json`) were not guaranteed.

## Minimal fix
1. `src/ji_engine/pipeline/runner.py`
- Initialize `providers`/`openai_only` with safe defaults before startup.
- Seed a default `stage_context` before `_finalize(...)` so finalize is safe even on startup failures.
- Move `_resolve_providers(args)` into the `try:` block and update `flag_payload["providers"]` after successful resolution.
- Preserve startup-provider failure contract: after finalization, provider-selection failures still re-raise `SystemExit(2)` (`raise ... from None`) for compatibility with existing callers/tests.

2. `tests/test_run_health_artifact.py`
- Added `test_provider_availability_written_when_no_enabled_providers`:
  - Uses a providers config with `openai` disabled.
  - Asserts `SystemExit(2)` is raised.
  - Asserts `run_health` exists (`status=failed`, `failed_stage=startup`).
  - Asserts `provider_availability_v1.json` exists and validates schema.
  - Asserts zero-provider state is explicit via `openai.enabled=false`, `availability=unavailable`, `reason_code=not_enabled`.

3. `docs/OPS_RUNBOOK.md`
- Updated provider availability guidance to reflect terminal-run invariant and fail-closed early-failure behavior.

## Commands run
```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_run_health_artifact.py tests/test_run_daily_provider_selection.py tests/test_provider_selection.py
.venv/bin/python -m ruff check src scripts tests
./scripts/audit_determinism.sh
python3 scripts/ops/check_dr_docs.py
python3 scripts/ops/check_dr_guardrails.py
```

## Results
- Tests: `20 passed`
- Ruff lint: PASS
- Determinism audit: PASS
- DR docs coherence: PASS
- DR guardrails: PASS

## Determinism / schema notes
- No schema version changes.
- No artifact format changes.
- Behavior change is control-flow only: startup provider-resolution failures now finalize deterministically and emit the existing artifact contract.
