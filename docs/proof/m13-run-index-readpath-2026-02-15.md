# Milestone 13 Proof: Run Index Read-Path Migration (2026-02-15)

## Change Receipt

Read-path migrated:
- `src/ji_engine/pipeline/runner.py::_resolve_latest_run_ranked`

Before:
- scanned `state/runs` directories and inspected per-run files to locate a baseline ranked artifact.

After:
- queries SQLite run index (`run_index_v1`) via `list_runs_as_dicts(...)` with explicit ordering
  `created_at DESC, run_id DESC`, then resolves the first matching ranked artifact path.
- retains legacy directory scan as a compatibility fallback if index lookup fails or returns no usable candidate.

Determinism contract:
- ordering is explicit and stable (`created_at`, then `run_id`)
- same candidate-scoped behavior as prior path (`candidate_id` filtered in run index query)
- baseline selection remains fail-safe through legacy fallback.

## Lightweight Benchmark (Local, Non-CI Assertion)

Command executed:

```bash
./.venv/bin/python - <<'PY'
# fixture: 1000 synthetic runs, each with ranked artifact + run_index row
# compare legacy scan helper vs index-backed helper over 30 repetitions
PY
```

Output:

```text
fixture_runs=1000
repetitions=30
legacy_scan_avg_ms=15.421
indexed_lookup_avg_ms=1.519
speedup_x=10.15
```

Interpretation:
- index-backed lookup materially reduces baseline resolution latency for larger run sets.
- this receipt is observational only; CI does not assert wall-clock performance.
