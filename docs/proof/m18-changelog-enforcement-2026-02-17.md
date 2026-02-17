# M18 Proof: Changelog Enforcement in CI

Date: 2026-02-17

## Policy Chosen
Option A (minimal, low-busywork): require `CHANGELOG.md` when either condition is true:
- PR has label `release`
- `pyproject.toml` changed (version source of truth per `docs/RELEASE_PROCESS.md`)

If policy is not triggered, check is a no-op/pass.

## Implementation
- Script: `scripts/check_changelog_policy.py`
- Make target: `make changelog-policy`
- CI hook: `.github/workflows/ci.yml` (pull_request `fast` job)
  - fetches PR base ref
  - runs changelog policy check before dependency install/tests

Determinism notes:
- Uses only local git metadata (`git merge-base`, `git diff --name-only`) and GitHub event payload labels.
- No external APIs.

## Failure Message Contract
On failure, output is explicit and actionable:
- why it failed
- exactly what file to update (`CHANGELOG.md`)
- docs pointer (`docs/RELEASE_PROCESS.md`)

## Commands Executed
```bash
make format
make lint
make ci-fast
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_check_changelog_policy.py
.venv/bin/python scripts/check_changelog_policy.py --changed-file pyproject.toml
.venv/bin/python scripts/check_changelog_policy.py --changed-file pyproject.toml --changed-file CHANGELOG.md
```

## Observed Results
- `make lint`: pass
- `make ci-fast`: `663 passed, 16 skipped`
- `tests/test_check_changelog_policy.py`: `5 passed`

Policy fail simulation:
- command: `.venv/bin/python scripts/check_changelog_policy.py --changed-file pyproject.toml`
- result: exit code `1`
- output includes:
  - `ERROR: changelog policy check failed.`
  - `Required fix: update CHANGELOG.md in this PR.`
  - `Release process: docs/RELEASE_PROCESS.md`

Policy pass simulation:
- command: `.venv/bin/python scripts/check_changelog_policy.py --changed-file pyproject.toml --changed-file CHANGELOG.md`
- result: exit code `0`
- output: `pass: changelog updated`
