# Milestone 11 Proof - Artifact Model v2 Enforcement (2026-02-15)

## Scope
Turn M11 scaffolding into real enforcement at dashboard read-path. Artifact catalog + validation at serving boundaries.

## Where Enforcement Happens

- **`src/ji_engine/dashboard/app.py`**: `_enforce_artifact_model()` called from `run_artifact` endpoint before serving any artifact.
- **`src/ji_engine/artifacts/catalog.py`**: Catalog lookup, prohibition check (UI-safe), schema validation (replay_safe).

## What's Categorized

| Artifact key | Category |
|--------------|----------|
| run_summary.v1.json | ui_safe |
| run_health.v1.json | replay_safe |
| run_report.json | replay_safe |
| provider_availability_v1.json | ui_safe |
| *ranked_jobs*.json, *.csv | replay_safe |
| *ranked_families*.json | replay_safe |
| *shortlist*.md, *alerts* | replay_safe |
| *ai_insights*.json, *ai_job_briefs*.json | ui_safe |
| Other | uncategorized (fail-closed) |

## Example Failure Payload Shape

**Uncategorized (503):**
```json
{
  "error": "artifact_uncategorized",
  "artifact_key": "unknown_artifact.json",
  "run_id": "2026-01-22T00:00:00Z",
  "message": "Artifact not in catalog; fail-closed."
}
```

**UI-safe prohibition (500):**
```json
{
  "error": "ui_safe_prohibition_violation",
  "artifact_key": "ai_insights.cs.json",
  "run_id": "2026-01-22T00:00:00Z",
  "violations": ["jobs.jd_text"]
}
```

## Receipts (Commands Run)

```bash
make format   # pass
make lint     # pass
make ci-fast  # pass (621 passed, 15 skipped)
make gate     # pass (pytest + snapshot immutability + replay smoke)
```

## Tests Added

- `tests/test_artifact_catalog.py`: `get_artifact_category`, `validate_artifact_payload` (uncategorized, ui_safe prohibition)
- `tests/test_dashboard_app.py`: `test_dashboard_artifact_model_v2_categorized_artifacts_serve`, `test_dashboard_artifact_model_v2_uncategorized_fails_closed`, `test_dashboard_artifact_model_v2_ui_safe_prohibition_rejects_jd_text` (requires dashboard extras)

## What Did NOT Change

- docs/ROADMAP.md
- Scoring logic, pipeline ordering, snapshot fixtures, baseline artifacts
- Determinism, replay guarantees
