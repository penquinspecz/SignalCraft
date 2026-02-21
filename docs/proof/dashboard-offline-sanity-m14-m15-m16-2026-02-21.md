# Dashboard Offline Sanity Receipt (M14/M15/M16) — 2026-02-21

## Goal
Provide a deterministic, CI-friendly dashboard artifact sanity check that does not require dashboard extras (`fastapi`, `uvicorn`) or network installs.

## Scope
- Script: `scripts/dashboard_offline_sanity.py`
- Make target: `make dashboard-sanity`
- CI wiring: included in `make ci-fast`
- Test coverage: `tests/test_dashboard_offline_sanity.py`

## What Is Verified
- Artifact catalog classification (`ui_safe`) for:
  - `explanation_v1.json`
  - `ai_insights.cs.json`
  - `ai_job_briefs.cs.json`
  - `ai_job_briefs.cs.error.json`
- Artifact-model validation (`validate_artifact_payload`) for each key.
- Schema/contract checks:
  - `schemas/explanation.schema.v1.json`
  - `schemas/ai_insights_output.schema.v1.json`
  - `schemas/ai_job_brief.schema.v1.json` (applied to each brief entry)
  - explicit error-artifact contract for `ai_job_briefs.*.error.json`
- Forbidden-field scan (`assert_no_forbidden_fields`) to enforce no raw JD leakage.

## Commands
```bash
make dashboard-sanity
make ci-fast
make gate
```

## Expected Summary Shape
```text
dashboard_offline_sanity
status=ok
artifacts_checked=4
category_checks_passed=4
artifact_model_checks_passed=4
schema_checks_passed=4
forbidden_field_checks_passed=4
```

## Determinism Notes
- Uses fixed in-memory fixture payloads (no network, no time-dependent randomization).
- Summary output order and counters are stable.
- No artifact path or schema contract modifications in this change.

## Validation Results
- `make dashboard-sanity`: PASS
- `make ci-fast`: `707 passed, 16 skipped`
- `make gate`: `707 passed, 16 skipped`
- Snapshot immutability: PASS
- Replay smoke: PASS
