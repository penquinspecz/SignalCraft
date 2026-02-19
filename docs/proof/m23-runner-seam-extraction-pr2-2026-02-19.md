# M23 Runner Seam Extraction PR2 (2026-02-19)

## Scope
Second low-coupling extraction from `runner.py`: redaction guard logic.

## Extraction
- New module: `src/ji_engine/pipeline/redaction_guard.py`
- Moved functions:
  - `redaction_enforce_enabled()`
  - `redaction_guard_text(path, text)`
  - `redaction_guard_json(path, payload)`

## Runner Compatibility
- `src/ji_engine/pipeline/runner.py` keeps compatibility wrappers:
  - `_redaction_enforce_enabled()`
  - `_redaction_guard_text(...)`
  - `_redaction_guard_json(...)`
- Existing runner call sites remain unchanged.

## LOC Delta
- `runner.py` before: `6079` lines
- `runner.py` after: `6073` lines
- Net: `-6` lines from runner, with logic now isolated in a dedicated seam module.

## Tests Added
- `tests/test_runner_redaction_enforcement.py`
  - `test_redaction_module_guard_json_fail_closed_when_enforced`
  - `test_redaction_module_guard_text_warns_when_not_enforced`

These complement existing runner-wrapper tests to prove behavior parity during extraction.
