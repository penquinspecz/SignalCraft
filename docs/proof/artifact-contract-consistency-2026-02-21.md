# Artifact Contract Consistency Guardrail — 2026-02-21

## Goal
Add a deterministic CI-fast test that enforces consistency between:
- artifact catalog registration
- schema files under `schemas/`
- pipeline artifact path helpers
- dashboard schema-version exposure for applicable artifacts

## Added Test
- `tests/test_artifact_contract_registry.py`

## Guarantees
- UI-safe catalog artifacts are validated against expected schema files:
  - `run_summary.v1.json` -> `schemas/run_summary.schema.v1.json`
  - `provider_availability_v1.json` -> `schemas/provider_availability.schema.v1.json`
  - `explanation_v1.json` -> `schemas/explanation.schema.v1.json`
  - `ai_insights.cs.json` -> `schemas/ai_insights_output.schema.v1.json`
  - `ai_job_briefs.cs.json` -> `schemas/ai_job_brief.schema.v1.json`
- Dashboard schema-version mapping is enforced for applicable UI-safe artifacts.
- Canonical run-artifact path helpers are present and stable for UI-safe artifacts.
- Guarded schema/artifact set has no orphan registrations.

## Notes
- No runtime behavior changes.
- No schema format changes.
- Deterministic ordering: all catalog/schema assertions use sorted collections.

## Validation
```bash
make lint
make ci-fast
```
