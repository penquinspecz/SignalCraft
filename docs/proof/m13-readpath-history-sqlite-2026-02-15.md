# Milestone 13 Proof: History Read-Path SQLite Migration (2026-02-15)

## Change Receipt

Read-path migrated:
- `scripts/report_changes.py::_list_runs(profile)`

Before:
- Scanned `HISTORY_DIR` with `rglob(profile)` and `glob("*.json")` to list runs for a profile.

After:
- Uses `RunRepository.list_runs_for_profile(candidate_id, profile)` which reads from SQLite index (RunRepository's run_index table).
- Returns runs ordered by index (newest first), then reversed to preserve report_changes semantics (oldest-first for `_get_previous_run`).
- Retains legacy history scan as fallback when index returns no runs (e.g., index not built, flat metadata layout).

## RunRepository Additions

- `list_runs_for_profile(candidate_id, profile, limit)` — filters `list_runs` by profile (from index payload `providers[*].profiles`).
- `_profiles_from_run_payload(payload)` — helper to extract profile names from index.json structure.

## Determinism Contract

- Ordering: index returns `timestamp DESC, run_id DESC`; report_changes expects oldest-first, so result is reversed.
- Same profile-scoped behavior as prior path.
- Legacy fallback preserves behavior when index is empty or unavailable.

## Verification

```bash
make format
make lint
make ci-fast
make gate
.venv/bin/python -m pytest tests/test_report_changes.py tests/test_run_repository.py -v
```

## Evidence Paths

- `tests/test_report_changes.py::test_list_runs_uses_index_when_available` — proves index-backed path is used when run dirs with index.json exist.
- `tests/test_run_repository.py::test_list_runs_for_profile_uses_index` — proves `list_runs_for_profile` filters by profile from index payload.
