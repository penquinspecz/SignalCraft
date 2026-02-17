# P2 Fix Proof: Profile-Complete Run Selection (2026-02-17)

## Objective

Fix `RunRepository.list_runs_for_profile` so profile filtering is logically correct under mixed-profile history, while preserving bounded and deterministic behavior.

## Problem

Previous behavior truncated first (`list_runs(limit=N)`) and then filtered by profile.
If many recent runs were for other profiles, profile-specific history was under-selected.

## Updated Behavior

`list_runs_for_profile` now:
- reads run index rows in deterministic pages
- ordering is unchanged and explicit: `timestamp DESC, run_id DESC` (newest-first)
- filters each page by profile
- continues paging until either:
  - `limit` matching runs are collected, or
  - available runs are exhausted

## Boundedness

- result count remains bounded by `limit` (clamped to `1..1000`)
- page size is fixed and bounded (`200` max)
- memory stays bounded to one page plus collected result rows
- full scan occurs only when necessary to satisfy correctness for sparse profiles

## Files Changed

- `src/ji_engine/run_repository.py`
- `tests/test_run_repository.py`

## Regression Coverage

Added deterministic tests for:
- many mixed-profile runs where non-matching runs dominate early pages
- requested profile runs found beyond the first page
- exhaustive behavior when requested `limit` exceeds total matches

## Validation

- `make format`
- `make lint`
- `make ci-fast`
- `make gate`
