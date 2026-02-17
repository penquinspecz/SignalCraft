# M13: No Run Filesystem Scan Outside RunRepository (2026-02-15)

## Summary

Eliminated remaining runtime filesystem scans for run discovery/metadata outside RunRepository. RunRepository is now the only code path that scans RUN_METADATA_DIR.

## rg Before (run-related hits in src/ scripts/)

```
src/ji_engine/pipeline/runner.py:    for run_dir in run_root.iterdir():
src/ji_engine/semantic/step.py:    per_profile_paths = sorted(semantic_dir.glob("scores_*.json"), ...)
scripts/prune_state.py:    reports = [p for p in runs_dir.glob("*.json") if p.is_file()]
```

## rg After

```
src/ji_engine/run_repository.py:    paths = sorted((p for p in runs_dir.glob("*.json") ...)  # list_run_metadata_paths_from_dir
src/ji_engine/run_repository.py:    for path in sorted(root.glob("*.json"), ...)              # list_run_metadata_paths
src/ji_engine/run_repository.py:    for run_dir in sorted((p for p in root.iterdir() ...)     # _scan_runs_from_filesystem
src/ji_engine/semantic/step.py:    per_profile_paths = sorted(semantic_dir.glob(...))        # fallback when provider_profile_pairs=None
```

## Migrated Call-Sites

| Location | Before | After | Why Safe |
|----------|--------|-------|----------|
| `runner.py::_resolve_latest_run_ranked_legacy_scan` | `run_root.iterdir()` | `_run_repository().list_run_dirs()` | Same semantics; RunRepository encapsulates scan |
| `semantic/step.py::finalize_semantic_artifacts` | `semantic_dir.glob("scores_*.json")` | `provider_profile_pairs` param; resolve paths from (provider, profile) | Caller knows provider/profile; no scan when pairs provided |
| `prune_state.py::_sorted_run_reports` | `runs_dir.glob("*.json")` | `list_run_metadata_paths_from_dir(runs_dir)` | Centralized in run_repository |

## Intentionally Left (Not Run Metadata)

| Location | Reason |
|----------|--------|
| `history_retention.py` iterdir on profile_runs, profile_daily | History pointer structure (history/{profile}/runs, history/{profile}/daily), not RUN_METADATA_DIR |
| `report_changes.py` HISTORY_DIR.rglob | History-based run discovery fallback; different tree |
| `prune_state.py` history_dir.rglob, history_dir.glob, latest_dir.iterdir | History retention; HISTORY_DIR, not runs |
| `run_repository.py` glob/iterdir | Implementation of the seam; only allowed scanner |
| `proof/onprem.py`, `scripts/ops/*` | Bundle/infra receipts, not run metadata |
| `enrich_jobs.py` jobs_dir.glob | Snapshot jobs dir, not runs |

## Enforcement Test

`tests/test_m13_no_run_filesystem_scan_repo_wide.py`:

- Monkeypatches `Path.iterdir` and `Path.glob` to raise when called on RUN_METADATA_DIR by non-RunRepository code
- Exercises: `_resolve_latest_run_ranked_legacy_scan`, `finalize_semantic_artifacts`, `plan_prune`
- RunRepository calls are allowed via `_is_run_repository_caller()` stack check

## Validation

```bash
make format && make lint && make ci-fast && make gate
```

## Contract

- Milestone moved; determinism unchanged; replay unchanged; no snapshot baseline changes.
- Run discovery and run metadata resolution go through RunRepository only.
