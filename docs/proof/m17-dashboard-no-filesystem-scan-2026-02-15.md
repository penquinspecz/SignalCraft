# M17: Dashboard No-Filesystem-Scan Guarantees (2026-02-15)

## Summary

Expands "no filesystem scan" guarantees for common dashboard read paths. Migrated remaining glob-based resolution to RunRepository/index-backed resolution.

## Paths Migrated

| Path | Before | After |
|------|--------|-------|
| `_load_first_ai_prompt_version` | `run_dir.glob("ai_insights.*.json")` | `index.artifacts` → `RUN_REPOSITORY.resolve_run_artifact_path` |
| `run_semantic_summary` (scores) | `semantic_dir.glob(f"scores_*_{profile}.json")` | `index.providers` / `run_report.outputs_by_provider` / `index.artifacts` → `RUN_REPOSITORY.resolve_run_artifact_path` |
| `run_semantic_summary` (summary) | `semantic_dir / "semantic_summary.json"` | `RUN_REPOSITORY.resolve_run_artifact_path(run_id, "semantic/semantic_summary.json", ...)` |

## Forbidden Patterns

```bash
# Dashboard must not use these on run metadata dir or run subdirs:
rg '\.glob\(' src/ji_engine/dashboard/
rg '\.iterdir\(' src/ji_engine/dashboard/
rg 'listdir' src/ji_engine/dashboard/
rg '\.rglob\(' src/ji_engine/dashboard/
```

Expected: no matches (or only in comments).

## Verification Steps

```bash
# 1. Unit tests
make format
make lint
make ci-fast
make gate

# 2. Regression test (requires dashboard extras: pip install -e '.[dashboard]')
PYTHONPATH=src .venv/bin/python -m pytest tests/test_dashboard_no_filesystem_scan.py -v

# 3. Forbidden pattern check
rg '\.glob\(' src/ji_engine/dashboard/ && echo "FAIL: glob found" || echo "OK: no glob"
rg '\.iterdir\(' src/ji_engine/dashboard/ && echo "FAIL: iterdir found" || echo "OK: no iterdir"
```

## Regression Test

`tests/test_dashboard_no_filesystem_scan.py::test_dashboard_run_detail_and_semantic_summary_use_index_not_glob`:

- Monkeypatches `Path.glob` to raise when invoked on run metadata dir or any subdir
- Calls `GET /runs/{run_id}` (run_detail) and `GET /runs/{run_id}/semantic_summary/{profile}`
- Asserts 200 and correct response shape
- Proves endpoints use index-backed resolution (no glob)

## Fallbacks

- **ai_insights**: Only from `index.artifacts`; no fallback (artifacts must be in index)
- **semantic scores**: 1) `index.providers`, 2) `run_report.outputs_by_provider`, 3) `index.artifacts` keys matching `semantic/scores_*_{profile}.json`
