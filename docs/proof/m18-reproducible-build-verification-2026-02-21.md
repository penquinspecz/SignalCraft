# M18 Reproducible Build Verification (2026-02-21)

## Scope
Close Milestone 18 DoD item: **"Reproducible build instructions verified"**.

## Environment Summary
- OS: macOS (arm64)
- Python: `python3 --version` -> `Python 3.14.3`
- Baseline commit: `b45cf1c845314da49e2fff95d769923d523bbb42`
- Clean-room method: fresh worktree/checkout with no pre-existing `.venv`

## Deterministic Procedure (repo-relative)
From repo root:

```bash
make tooling-sync
make lint
make ci-fast
make gate
```

Notes:
- `make tooling-sync` is the bootstrap step and now installs both runtime + dev lockfiles.
- Dashboard extras are not required for `make ci-fast`/`make gate`.
- Dashboard contract sanity remains covered via `make dashboard-sanity` inside `make ci-fast`.

## Execution Results
1. `make tooling-sync`
- PASS
- Created `.venv` with `python3`
- Installed pinned tooling and lockfile deps

2. `make lint`
- PASS

3. `make ci-fast`
- PASS
- `ruff`: PASS
- `dashboard_offline_sanity`: PASS (`artifacts_checked=6`)
- `pytest`: `720 passed, 17 skipped`

4. `make gate`
- PASS
- `pytest`: `720 passed, 17 skipped`
- snapshot immutability: PASS
- replay smoke: PASS (`checked=6`, `mismatched=0`, `missing=0`)

## Gotchas + Deterministic Handling
Observed gap before fix:
- Clean-room bootstrap initially failed because `make tooling-sync` assumed `python` existed.
- Clean-room `ci-fast` initially failed because bootstrap only installed `requirements-dev.txt`, not runtime lockfile dependencies.

Fixes applied in this change:
- `Makefile` now bootstraps `.venv` with `BOOTSTRAP_PY` defaulting to `python3`.
- `make tooling-sync` now installs both `requirements.txt` and `requirements-dev.txt`.

These changes remove host alias assumptions and make clean-room setup reproducible with lockfile parity.
