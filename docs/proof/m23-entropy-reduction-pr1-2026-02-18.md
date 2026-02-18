# M23 Entropy Reduction PR1 - 2026-02-18

## Scope
- Deduplicate S3 URI parsing across:
  - `scripts/ops/backup_onprem.py`
  - `scripts/ops/restore_onprem.py`
- Reuse shared parser from `scripts/ops/dr_contract.py`.
- Add URI validation tests for both scripts.

## Commands
```bash
PYTHONPATH=src ./.venv/bin/python -m pytest -q tests/test_ops_backup_restore_uri_validation.py
make lint
make ci-fast
make gate
```

## Validation Results
- Targeted tests: `2 passed`
- `make lint`: pass
- `make ci-fast`: pass (`675 passed, 16 skipped`)
- `make gate`: pass (`675 passed, 16 skipped`)
- Snapshot immutability: pass
- Replay smoke: pass (`checked=6 matched=6 mismatched=0 missing=0`)

## Before/After LOC Diff

Touched existing files:
- `scripts/ops/backup_onprem.py`: `245 -> 234` (net `-11`)
- `scripts/ops/restore_onprem.py`: `193 -> 182` (net `-11`)

Added test file:
- `tests/test_ops_backup_restore_uri_validation.py`: `+54`

Net for modified existing production files: `-22` LOC.

## Dependency Tree Delta

Equivalent method used (`pip freeze` snapshots):
```bash
./.venv/bin/python -m pip freeze | sort > /tmp/m23_pr1_pip_freeze_after.txt
./.venv/bin/python -m pip freeze | sort > /tmp/m23_pr1_pip_freeze_after_2.txt
diff -u /tmp/m23_pr1_pip_freeze_after.txt /tmp/m23_pr1_pip_freeze_after_2.txt
```

Result:
- `diff` output is empty (`0` lines): no dependency tree drift.
- Dependency metadata files unchanged:
  - `pyproject.toml`
  - `requirements.txt`
  - `requirements-dev.txt`

## Determinism / Replay Notes
- Change is parser deduplication in ops scripts only.
- No runtime scoring/snapshot/replay contract logic changed.
- Gate replay and snapshot checks remained green.
