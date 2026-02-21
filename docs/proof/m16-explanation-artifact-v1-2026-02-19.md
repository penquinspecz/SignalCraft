# M16 Explainability Artifact v1 Receipt (2026-02-19)

## Scope
- Milestone: M16 Explainability v1
- Invariant: emit deterministic, UI-safe explanation artifact without raw JD text

## Evidence Paths
- Schema: `schemas/explanation.schema.v1.json`
- Artifact path (canonical run path): `state/candidates/<candidate_id>/runs/<sanitized_run_id>/artifacts/explanation_v1.json`
- Emission logic: `src/ji_engine/pipeline/runner.py`
- Artifact catalog/UI-safe enforcement: `src/ji_engine/artifacts/catalog.py`
- Dashboard schema-version exposure: `src/ji_engine/dashboard/app.py`
- Tests: `tests/test_explanation_artifact_v1.py`

## Contract Summary
- `schema_version` is fixed to `explanation.v1`.
- `top_jobs` ordering is deterministic:
  - sorted by `score_total` descending
  - tie-breaker `job_hash` ascending
  - `rank` is assigned from sorted order (1..N)
- Explanation data is derived only from deterministic scoring fields already produced (`score_hits` and score totals).
- No raw JD body/description/requirements/responsibilities fields are serialized.

## Sample Snippet (Redacted/Safe)
```json
{
  "schema_version": "explanation.v1",
  "run_id": "2026-02-19T12:00:00Z",
  "candidate_id": "local",
  "top_jobs": [
    {
      "job_hash": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
      "rank": 1,
      "score_total": 99.0,
      "top_positive_signals": [{"name": "boost_relevant", "value": 1, "weight": 10.0, "contribution": 10.0}],
      "top_negative_signals": [{"name": "penalty_low_level", "value": 1, "weight": -5.0, "contribution": -5.0}],
      "penalties": [{"name": "penalty_low_level", "amount": 5.0, "reason_code": "penalty_low_level"}],
      "notes": ["Low-level systems penalty applied."]
    }
  ]
}
```

## Validation Commands
```bash
PYTHONPATH=src /Users/chris.menendez/Projects/signalcraft/.venv/bin/python -m pytest -q tests/test_explanation_artifact_v1.py tests/test_artifact_catalog.py
PYTHONPATH=src /Users/chris.menendez/Projects/signalcraft/.venv/bin/python -m pytest -q tests/test_run_health_artifact.py tests/test_run_summary_artifact.py tests/test_dashboard_app.py -k "artifact_index_shape_and_schema_versions or run_health_written_on_success or run_summary_written_with_hashes_on_success"
make format
make lint
make ci-fast
make gate
```

## Results
- Targeted explanation/catalog tests: `8 passed`
- Targeted run-summary/run-health/dashboard checks: `2 passed, 1 skipped`
- `make ci-fast`: `699 passed, 16 skipped`
- `make gate`: `699 passed, 16 skipped`
- Snapshot immutability: PASS
- Replay smoke: PASS (all artifact hashes matched)
