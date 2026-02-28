# Milestone 34 Proof: UI v0 Screenshot (2026-02-28)

## Scope

Provide screenshot evidence for the new read-only UI v0 surface.

## Screenshot Artifact

- [m34-ui-v0-readonly-screenshot-2026-02-28.svg](./m34-ui-v0-readonly-screenshot-2026-02-28.svg)

The screenshot shows all required panels in the minimal read-only surface:
- Latest run summary
- Top jobs list
- Explanation view
- Provider availability panel
- Run health panel

## Endpoint Basis

UI v0 reads from documented API endpoints only:
- `GET /v1/ui/latest`
- `GET /ui`

## Invariants

- Read-only only (no mutation endpoints used)
- No raw JD keys exposed in UI payload
- Determinism unchanged
- Replay unchanged
- No snapshot baseline modification
