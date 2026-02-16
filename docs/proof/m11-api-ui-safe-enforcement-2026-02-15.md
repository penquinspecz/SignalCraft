# M11: API UI-Safe Enforcement (2026-02-15)

## Summary

Enforce UI-safe / replay-safe contracts on dashboard API boundary. All endpoints that return artifact-derived data either return UI-safe payloads (fail-closed) or index-only (no artifact bodies). No raw JD leakage.

**UI-safe endpoints fail closed**; redaction is used only for replay-safe/legacy compatibility.

## Endpoint Classification

| Endpoint | Mode | Enforcement |
|----------|------|-------------|
| GET /version | index-only | Metadata only; no artifact bodies |
| GET /healthz | index-only | Status only |
| GET /runs | index-only | Run index list; no artifact bodies |
| GET /runs/{run_id} | derived | `assert_no_forbidden_fields` (fail-closed) |
| GET /runs/{run_id}/artifact/{name} | artifact body | ui_safe: fail-closed; replay_safe: redact before serve |
| GET /runs/{run_id}/semantic_summary/{profile} | derived | `assert_no_forbidden_fields` (fail-closed) |
| GET /v1/latest | derived | `assert_no_forbidden_fields` (fail-closed) |
| GET /v1/runs/{run_id} | derived | `assert_no_forbidden_fields` (fail-closed) |
| GET /v1/runs/{run_id}/artifacts | index-only | Artifact index; no bodies |
| GET /v1/artifacts/latest/{provider}/{profile} | index-only | Paths/keys only |

## Forbidden Fields

- `jd_text`
- `description`
- `description_text`
- `descriptionHtml`
- `job_description`

## Back-Compat Strategy

- **UI-safe endpoints** (run_detail, run_semantic_summary, latest, run_receipt): Fail closed via `assert_no_forbidden_fields`. If forbidden keys present, return 500.
- **Replay-safe artifacts**: Served with `redact_forbidden_fields` before serve. Replay verification uses raw artifacts from disk; dashboard only serves redacted copies.
- **Uncategorized artifacts**: Continue to fail-closed (503) as before.

## Implementation

- `ji_engine.artifacts.catalog.assert_no_forbidden_fields(obj)`: Fail-closed; raises ValueError if forbidden keys found.
- `ji_engine.artifacts.catalog.redact_forbidden_fields(obj)`: Recursively strips forbidden keys; used only for replay-safe/legacy artifact serving.
- Dashboard: UI-safe endpoints use assert; run_artifact (replay_safe) uses redact.

## Tests

- `test_redact_forbidden_fields_removes_jd_keys`: Unit test for redact helper.
- `test_dashboard_api_no_raw_jd_leakage`: Parametrized over endpoints; asserts no forbidden keys in JSON response (requires dashboard extras).

## Validation

```bash
make format && make lint && make ci-fast && make gate
```
