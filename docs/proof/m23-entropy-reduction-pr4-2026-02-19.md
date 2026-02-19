# M23 Entropy Reduction PR4 (Dead Code) - 2026-02-19

## Scope
Remove dead helpers from `src/ji_engine/pipeline/runner.py` with provable no-reference evidence.

## Deleted Code
- `runner._unavailable_summary()`
- `runner._redaction_enforce_enabled()`
- now-unused import alias:
  - `redaction_enforce_enabled as _redaction_enforce_enabled_impl`

## Why These Are Dead
Reference proof commands:

```bash
rg -n "\\b_unavailable_summary\\b" -S src tests scripts
rg -n "\\b_redaction_enforce_enabled\\b" -S src tests scripts
rg -n "_redaction_enforce_enabled_impl" src/ji_engine/pipeline/runner.py src/ji_engine/pipeline/redaction_guard.py
```

Observed output:

```text
src/ji_engine/pipeline/runner.py:189:def _unavailable_summary() -> str:
src/ji_engine/pipeline/runner.py:560:def _redaction_enforce_enabled() -> bool:
src/ji_engine/pipeline/runner.py:74:    redaction_enforce_enabled as _redaction_enforce_enabled_impl,
src/ji_engine/pipeline/runner.py:561:    return _redaction_enforce_enabled_impl()
```

Interpretation:
- Each deleted symbol appeared only at its own definition (no call sites).
- The removed import alias was only used by the removed dead wrapper.

## Focused Test Added
- `tests/test_runner_dead_code_cleanup.py`
  - `test_removed_dead_runner_helpers_not_present`

This asserts the removed dead helpers are not reintroduced accidentally.

## Safety Notes
- No orchestration flow edits.
- No schema edits.
- No artifact filename/path edits.
- No run directory layout edits.
- No determinism/replay contract edits.

## Validation Commands
```bash
make format
make lint
make ci-fast
make gate
```
