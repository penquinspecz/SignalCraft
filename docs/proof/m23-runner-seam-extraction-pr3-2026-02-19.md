# M23 Runner Seam Extraction PR3 (2026-02-19)

## Scope
Third low-coupling extraction from `runner.py`: artifact path resolution helpers.

## Extraction
- New module: `src/ji_engine/pipeline/artifact_paths.py`
- Moved pure helper functions:
  - `run_metadata_path(run_metadata_dir, run_id)`
  - `run_health_path(run_dir)`
  - `run_summary_path(run_dir)`
  - `provider_availability_path(run_dir)`
  - `run_audit_path(run_dir)`

## Runner Compatibility
- `src/ji_engine/pipeline/runner.py` keeps compatibility wrappers:
  - `_run_metadata_path(run_id)`
  - `_run_health_path(run_id)`
  - `_run_summary_path(run_id)`
  - `_provider_availability_path(run_id)`
  - `_run_audit_path(run_id)`
- Existing runner call sites and orchestration flow remain unchanged.

## Why Safe
- Extracted helpers are deterministic path constructors only.
- No schema loading logic changed.
- No artifact filenames changed.
- No stage ordering, exception behavior, network behavior, or replay contracts changed.

## Focused Tests
- New file: `tests/test_artifact_paths.py`
  - `test_run_metadata_path_sanitizes_run_id`
  - `test_run_registry_paths_match_contract_filenames`

## Runner LOC Delta
- `runner.py` before: `6073` lines
- `runner.py` after: `6087` lines
- Net: `14` lines

## Validation
Commands:
```bash
make lint
make ci-fast
make gate
```

Results:
- `make lint`: pass
- `make ci-fast`: pass (`693 passed, 16 skipped`)
- `make gate`: pass (`693 passed, 16 skipped`, snapshot immutability pass, replay smoke pass)
