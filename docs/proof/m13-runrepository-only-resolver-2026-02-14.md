# M13: RunRepository as Only Resolver for Run Discovery

**Date:** 2026-02-14  
**Milestone:** 13  
**Goal:** RunRepository is the ONLY resolver used for run discovery in application code (dashboard + CLI + scripts); eliminate remaining filesystem scans/path-walking in the common path.

## Summary

Application code now uses RunRepository exclusively for run discovery. Direct directory scans (`iterdir`, `glob` on run metadata dir) are forbidden in the common path. Fallback scans remain explicit, bounded, and only when the index is empty or missing.

## Migrated Paths

| Path | Before | After |
|------|--------|-------|
| `src/ji_engine/pipeline/runner.py` `_resolve_latest_run_ranked` | `list_indexed_runs` (run_index state) + fallback `run_root.iterdir()` | `_run_repository().list_runs()`; fallback `_resolve_latest_run_ranked_legacy_scan` only when index empty |
| `src/ji_engine/pipeline/runner.py` `_enforce_run_log_retention` | `runs_dir.iterdir()` | `run_repository.list_run_dirs(candidate_id=...)` |
| `build/lib/jobintel/dashboard/app.py` `_list_runs` | `RUN_METADATA_DIR.iterdir()` + per-dir `index.json` read | `_RUN_REPOSITORY.list_runs()` |

## Forbidden Patterns

The following patterns are **forbidden** in application run discovery paths:

- `RUN_METADATA_DIR.iterdir()` or `run_metadata_dir.iterdir()`
- `RUN_METADATA_DIR.glob("*.json")` for run listing
- `run_root.iterdir()` for run discovery (pipeline baseline resolution)
- Direct `index.json` reads outside RunRepository for run listing

## Allowed Patterns

- **RunRepository methods:** `list_runs()`, `list_run_dirs()`, `resolve_run_dir()`, `resolve_run_artifact_path()`, etc.
- **Fallback scan:** `_resolve_latest_run_ranked_legacy_scan` and `_scan_runs_from_filesystem` — only when index is empty or missing; explicit, bounded.
- **Within run dir:** `run_dir.glob("ai_insights.*.json")` — artifact discovery within an already-resolved run dir, not run discovery.
- **Debug/ops scripts:** `scripts/prune_state.py`, `scripts/report_changes.py` — history retention and report tooling; keep scan, bounded and labeled.

## Verification

### Tests

```bash
pytest tests/test_m13_runrepository_only_resolver.py -v
pytest tests/test_run_index_readpath.py
pytest tests/test_run_daily_observability.py
```

### Enforcement Test

`tests/test_m13_runrepository_only_resolver.py::test_resolve_latest_run_ranked_uses_run_repository_not_direct_scan`:

- Monkeypatches `Path.iterdir` to raise when invoked on `RUN_METADATA_DIR`
- Asserts `_resolve_latest_run_ranked` still succeeds (uses RunRepository index)
- If code regressed to direct scan, the test would fail

### Ripgrep Snippets (no hits in common path)

```bash
# Direct iterdir on run metadata dir — should not appear in dashboard/pipeline/CLI
rg "RUN_METADATA_DIR\.iterdir|run_metadata_dir\.iterdir" src/ji_engine/dashboard src/ji_engine/pipeline
# (empty after migration)

# Pipeline run discovery
rg "run_root\.iterdir" src/ji_engine/pipeline/runner.py
# Only in _resolve_latest_run_ranked_legacy_scan (fallback, explicit)
```

## Determinism

- RunRepository `list_runs()` orders by `(timestamp DESC, run_id DESC)` — unchanged.
- `list_run_dirs()` derives from `list_runs()` — same ordering.
- Replay and snapshot baselines unchanged.
