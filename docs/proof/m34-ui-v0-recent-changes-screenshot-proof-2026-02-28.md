# Milestone 34 Proof: UI v0 Recent Changes Screenshot (2026-02-28)

## Scope

Capture updated UI v0 surface showing job-change analytics.

## Screenshot Artifact

- [m34-ui-v0-recent-changes-screenshot-2026-02-28.svg](./m34-ui-v0-recent-changes-screenshot-2026-02-28.svg)

## What Is Visible

- Existing read-only panels (latest run, top jobs, explanation, provider availability, run health)
- New `Recent Changes` panel
- Per-job `View Timeline` links (top jobs + recent changes)

## Endpoint Basis

- `GET /ui`
- `GET /v1/ui/latest`
- `GET /v1/jobs/{job_hash}/timeline`

## Invariants

- Read-only only (no mutation endpoints)
- No raw JD keys exposed in UI payload contract
- Determinism unchanged
- Replay unchanged
- No snapshot baseline modification
