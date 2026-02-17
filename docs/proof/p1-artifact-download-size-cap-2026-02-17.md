# P1 Fix Proof: Dashboard Artifact Download Size Cap (2026-02-17)

## Objective

Prevent memory-amplification/DoS in dashboard artifact downloads by enforcing one bounded payload-size policy across all artifact types.

## Policy

- Endpoint: `GET /runs/{run_id}/artifact/{name}`
- Single cap source: `JOBINTEL_DASHBOARD_MAX_JSON_BYTES` (default `2097152`)
- Enforcement:
  - `stat().st_size` is checked before any artifact body read for **all** artifact types.
  - Oversized artifacts return `413` with compact JSON detail:
    - `{"error":"artifact_too_large","message":"Artifact payload too large","max_bytes":<limit>}`
- Serving behavior:
  - JSON artifacts: model validation and replay-safe redaction path unchanged.
  - Non-JSON artifacts: served via streaming `FileResponse` after cap check.

## Security/Determinism Notes

- Path traversal protections remain in `_resolve_artifact_path` (name sanitation + index mapping + resolver containment checks).
- No new network behavior introduced.
- Bounded read policy is deterministic and environment-configured only by explicit cap env var.

## Affected Files

- `src/ji_engine/dashboard/app.py`
- `tests/test_dashboard_app.py`

## Test Evidence Added

- Oversized non-JSON artifact returns `413` and is rejected before body read.
- Oversized JSON artifact returns `413` and is rejected before body read.
- Small non-JSON artifact still returns `200` and expected content type/body.

## Validation Commands

- `make format`
- `make lint`
- `make ci-fast`
- `make gate`
