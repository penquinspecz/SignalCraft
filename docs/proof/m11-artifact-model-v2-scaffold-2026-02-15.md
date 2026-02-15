# Milestone 11 Proof - Artifact Model v2 Scaffold (2026-02-15)

## Scope
Contract-first scaffolding for UI-safe vs replay-safe artifact categories. No pipeline changes to emit new artifacts; no backward-incompatible changes to existing payloads.

## What Changed

### Schemas
- `schemas/ui_safe_artifact.schema.v1.json` — defines UI-safe shape; prohibits raw JD fields (`jd_text`, `description`, `description_text`, `descriptionHtml`, `job_description`).
- `schemas/replay_safe_artifact.schema.v1.json` — defines replay-safe shape; requires `run_id`, `hashes`, `artifact_type`.

### Tests
- `tests/test_artifact_model_v2.py`:
  - Schema load and validation for minimal UI-safe and replay-safe payloads.
  - Prohibition tests: payloads with `jd_text` or `description` fail UI-safe validation.
  - `test_insights_input_alignment_ui_safe_no_raw_jd` — aligns with `test_insights_input_excludes_raw_jd_text`.
  - `test_existing_artifacts_categorization_documented` — documents current state (not yet categorized).

### Documentation
- `docs/ARTIFACT_MODEL.md` — defines UI-safe vs replay-safe split, prohibited fields, backward compatibility policy, current artifact categorization table.
- `docs/ROADMAP.md` — Milestone 11 DoD updated; schema and compatibility items marked done.

## What Did NOT Change

- Pipeline (`scripts/run_daily.py`) — no emission of new artifact types.
- Existing artifact payloads — no schema changes to `run_summary`, `run_health`, `run_report`, etc.
- Run summary pointers — no new `primary_artifacts` keys; backward compatible.
- Snapshot baselines — no modification.
- Determinism — unchanged.
- Replay — unchanged.

## Validation Receipts
- `make format`
- `make lint`
- `make ci-fast`
- `make gate`
