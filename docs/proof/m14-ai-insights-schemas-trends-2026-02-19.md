# M14 AI Insights Schemas + Trends Receipt (2026-02-19)

## Scope
- Add versioned deterministic input schema for insights.
- Add deterministic 7/14/30-day trend aggregation from structured fields only.
- Enforce strict output schema with fail-closed behavior.
- Keep cache-key contract stable around structured input hash + prompt version.

## Evidence Paths
- Input schema: `schemas/ai_insights_input.schema.v1.json`
- Output schema: `schemas/ai_insights_output.schema.v1.json`
- Input builder + trend engine: `src/ji_engine/ai/insights_input.py`
- Output enforcement + fail-closed handling: `src/jobintel/ai_insights.py`
- Prompt version bump: `docs/prompts/weekly_insights_v4.md`
- Tests:
  - `tests/test_ai_insights_schema_enforcement.py`
  - `tests/test_ai_insights_trends.py`
  - `tests/test_ai_insights.py`
  - `tests/test_insights_input.py`

## Contract Notes
- `insights_input.<profile>.json` now uses `schema_version="ai_insights_input.v1"` and includes:
  - `candidate_id`
  - `window_days` = `[7, 14, 30]`
  - `job_counts` and deterministic trend windows
  - `top_companies`, `top_titles`, `top_locations`, `top_skills`
  - scoring summary (`mean`, `median`, `top_n_scores`)
  - optional explanation aggregates when `artifacts/explanation_v1.json` exists
- `ai_insights.<profile>.json` now uses `schema_version="ai_insights_output.v1"` and includes exactly 5 actions with structured evidence field references.
- Fail-closed behavior:
  - invalid output writes `ai_insights.<profile>.error.json`
  - final emitted output status becomes `error` with schema-error metadata
  - pipeline does not crash on schema validation failure.

## Determinism + Privacy
- No raw JD fields are read for token extraction or trends.
- Structured token extraction uses only stable job fields (`title/company/location/team/department/role_band`).
- Trend windows are deterministic by sorted run timestamp + run_id order.
- Cache key remains deterministic with the same shape and still includes:
  - `structured_input_hash` (`input_hash`)
  - `prompt_version`
- Prompt version bumped: `weekly_insights_v3` -> `weekly_insights_v4`.

## Commands Executed
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_insights_input.py tests/test_ai_insights.py tests/test_ai_insights_schema_enforcement.py tests/test_ai_insights_trends.py
make format
make lint
make ci-fast
make gate
```
