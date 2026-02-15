# Chore: Stop Tracking Build Artifacts (2026-02-15)

## Summary

Removed `build/` from git tracking. These are generated/copied artifacts from package builds, not source.

## What Was Removed

- **build/** (57 files): `build/lib/ji_engine/...`, `build/lib/jobintel/...`
- Files were copies of `src/` layout; not authoritative source

## Why

- Build artifacts should not be version-controlled
- Reduces noise in PRs (e.g. accidental edits to build/lib/...)
- `.gitignore` now includes `build/` and `dist/` to prevent re-adding

## Verification

```bash
git ls-files | rg '^build/'  # empty after this change
make format && make lint && make ci-fast && make gate
```

## Related

- PR #150 previously modified `build/lib/jobintel/dashboard/app.py`; that change was reverted (build/ is generated junk)
- Source of truth for dashboard: `src/ji_engine/dashboard/app.py`
