# M22 Follow-on: Redaction Mode Contract (2026-02-18)

## Goal
Enforce an explicit production policy that requires fail-closed redaction mode without changing local/default runner behavior.

## Policy
- Runtime default remains unchanged: runner redaction guard is warn-only unless `REDACTION_ENFORCE=1`.
- Production preflight contract now requires `REDACTION_ENFORCE=1`.

## Enforcement Points Added
- `scripts/preflight_env.py`
  - Added `--deployment-env` (`dev|prod` normalized).
  - In `prod`, required contract includes `REDACTION_ENFORCE=1`.
- `ops/k8s/overlays/live/patch-configmap.yaml`
  - Sets `REDACTION_ENFORCE: "1"` for live overlay.
- `docs/OPS_RUNBOOK.md`
  - Adds explicit prod preflight + redaction contract steps.

## Tests
- `tests/test_preflight_env.py::test_preflight_prod_requires_redaction_enforce`
- `tests/test_preflight_env.py::test_preflight_prod_inferred_from_env`
- `tests/test_k8s_overlay_wrappers.py::test_live_overlay_sets_redaction_enforce_fail_closed`

## Validation Commands
```bash
make format
make lint
make ci-fast
make gate
```
