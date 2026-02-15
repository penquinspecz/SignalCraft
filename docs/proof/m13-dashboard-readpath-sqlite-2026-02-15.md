# Milestone 13 Proof - Dashboard Run Read Path to SQLite (2026-02-15)

## Endpoint Migrated

**GET /runs** (and **GET /runs?candidate_id=...**)

Previously: `_list_runs` called `RUN_REPOSITORY.list_run_dirs()`, then for each run dir read `index.json` from disk, then sorted. This caused N filesystem reads (one per run) plus a directory iteration.

Now: `_list_runs` calls `RUN_REPOSITORY.list_runs()` directly. Index-first: payloads come from SQLite when index exists. No per-run index.json reads in the common case.

## Scan Removed

- **Before**: For each run dir from `list_run_dirs`, read `path / "index.json"` from disk.
- **After**: Single `list_runs()` call; payloads from SQLite `payload_json` column when index is warm.

## Perf Sanity

When index exists and is warm:
- **Before**: O(N) index.json reads (N = number of runs)
- **After**: O(1) SQLite query; no per-run file reads

Rough comparison (index warm, 50 runs): before ~50 file opens + reads; after ~1 SQLite query. Scan avoided in common case.

## Ordering

Preserved: `ORDER BY timestamp DESC, run_id DESC` (newest first). Same as repo contract.

## Receipts

```bash
make format   # pass
make lint    # pass
make ci-fast # pass
make gate    # pass
```

## Tests Added

- `test_list_runs_uses_index_without_filesystem_scan`: Proves index path used when index exists (monkeypatch scan to raise; list_runs still succeeds).
- `test_list_runs_ordering_deterministic`: Proves ordering is timestamp DESC, run_id DESC.

## Fallback

When index is empty or read fails, `list_runs` falls back to `_scan_runs_from_filesystem`. Same behavior as before; explicit and test-covered in `test_corrupt_index_triggers_safe_rebuild`.
