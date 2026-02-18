# M23 Runner Seam Extraction PR1 - 2026-02-18

## Runner Decomposition Plan (Module Map)
Current monolith: `src/ji_engine/pipeline/runner.py`.

Proposed responsibility split:
- Stage orchestration:
  - `src/ji_engine/pipeline/orchestrator.py`
  - `src/ji_engine/pipeline/stage_context.py`
- Artifact emission:
  - `src/ji_engine/pipeline/artifacts_writer.py`
  - `src/ji_engine/pipeline/run_pathing.py` (implemented seam)
- Failure handling:
  - `src/ji_engine/pipeline/failure_policy.py`
  - `src/ji_engine/pipeline/run_health_builder.py`
- Redaction guard:
  - `src/ji_engine/pipeline/redaction_guard.py`
- Provider availability:
  - `src/ji_engine/pipeline/provider_availability.py`
- Run report / receipts:
  - `src/ji_engine/pipeline/run_reporting.py`
  - `src/ji_engine/pipeline/proof_receipts.py`
- Cost telemetry:
  - `src/ji_engine/pipeline/cost_telemetry.py`

## PR1 Extraction Choice
Chosen seam: run path helpers (pure, deterministic, low coupling).

Why this seam:
- Pure string/path transformations only.
- No network IO and no mutable shared state.
- Existing tests already exercise run-id/path behavior through runner call sites.

## Extraction Implemented
New module:
- `src/ji_engine/pipeline/run_pathing.py`

Functions moved:
1. `runner._sanitize_run_id` -> `run_pathing.sanitize_run_id`
2. `runner._summary_path_text` logic -> `run_pathing.summary_path_text`
3. `runner._resolve_summary_path` logic -> `run_pathing.resolve_summary_path`

Compatibility approach:
- `runner.py` imports moved helpers.
- Thin wrappers retained for `_summary_path_text` and `_resolve_summary_path` to keep call sites unchanged.
- `runner._sanitize_run_id` remains available via imported alias, preserving existing tests.

## Runner LOC Delta
- Before: `6080`
- After: `6075`

## Tests
Added:
- `tests/test_run_pathing.py`
  - `test_sanitize_run_id_normalizes_timestamp_separators`
  - `test_summary_path_text_prefers_repo_relative`
  - `test_resolve_summary_path_supports_absolute_and_repo_relative`

Compatibility check:
- `tests/test_run_index_readpath.py` passes unchanged.

## Validation
Commands:
```bash
make lint
make ci-fast
make gate
```

Results:
- `make lint`: pass
- `make ci-fast`: pass (`681 passed, 16 skipped`)
- `make gate`: pass (`681 passed, 16 skipped`, snapshot immutability pass, replay smoke pass)
