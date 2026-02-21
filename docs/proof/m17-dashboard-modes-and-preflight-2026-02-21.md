# M17 Dashboard Modes + Preflight Receipt — 2026-02-21

## Goal
Clarify deterministic dashboard operation modes without adding CI network requirements.

## Supported Modes
- Minimal/offline mode: `make dashboard-sanity`
  - deterministic artifact API sanity checks only
  - no FastAPI/Uvicorn dependency required
- Full dashboard mode: `make dashboard`
  - requires local extras install: `pip install -e ".[dashboard]"`

## Deterministic Failure Behavior
`make dashboard` preflights `fastapi` + `uvicorn` and exits code `2` if missing with actionable guidance:

```text
Dashboard deps missing (fastapi, uvicorn). Install with: pip install -e '.[dashboard]'
```

## Evidence
- Docs: `docs/DASHBOARD.md`
- Runbook pointer: `docs/OPS_RUNBOOK.md`
- Test: `tests/test_make_dashboard_missing_extras.py`
- Make targets: `Makefile` (`dashboard`, `dashboard-sanity`)

## Validation
```bash
make lint
make ci-fast
```
