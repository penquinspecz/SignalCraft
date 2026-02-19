# M15 Job Brief Schema Enforcement Receipt (2026-02-19)

## Scope
- Add explicit job brief schema contract.
- Enforce brief validation in generation path.
- Fail-closed on invalid brief payloads.
- Preserve deterministic cache key contract based on job hash + profile hash + prompt version.

## Evidence Paths
- Schema: `schemas/ai_job_brief.schema.v1.json`
- Enforcement code: `src/jobintel/ai_job_briefs.py`
- Schema tests: `tests/test_ai_job_briefs_schema.py`
- Existing behavior coverage: `tests/test_ai_job_briefs.py`

## Enforcement Behavior
- Every brief payload is validated against `ai_job_brief.v1`.
- On schema validation failure:
  - generation is fail-closed (`status=error`, `reason=job_brief_schema_validation_failed`)
  - no partial briefs are emitted (`briefs=[]`)
  - structured error artifact is written: `ai_job_briefs.<profile>.error.json`
- Cached briefs are re-validated before reuse; invalid cache entries trigger fail-closed handling.

## Cache Determinism
- Cache key is derived from:
  - `job_hash`
  - `profile_hash`
  - `prompt_version`
- This preserves deterministic cache behavior and avoids non-deterministic inputs.

## Validation Commands
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_ai_job_briefs.py tests/test_ai_job_briefs_schema.py
make lint
make ci-fast
make gate
```

## Results
- Targeted briefs tests: `5 passed`
- `make ci-fast`: `700 passed, 16 skipped`
- `make gate`: `700 passed, 16 skipped`
- Snapshot immutability: PASS
- Replay smoke: PASS
