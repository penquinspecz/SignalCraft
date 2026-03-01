# Milestone Rehome Proof (2026-03-01)

## Scope
Programmatic PR milestone rehoming from catch-all milestones to roadmap milestones using:
- `scripts/dev/rehoming_milestones.py`
- GitHub API only (`gh api` transport)

## Commands Run
- `.venv/bin/python scripts/dev/rehoming_milestones.py --dry-run`
- `.venv/bin/python scripts/dev/rehoming_milestones.py --apply`
- `.venv/bin/python scripts/dev/rehoming_milestones.py --verify`
- `.venv/bin/python scripts/dev/rehoming_milestones.py --apply` (idempotent cleanup pass)
- `.venv/bin/python scripts/dev/rehoming_milestones.py --verify`

## Rehome Counts (first apply)
- Total PRs scanned: `271`
- PRs changed: `263`

Moved out of catch-all milestones:
- `Infra & Tooling`: `28`
- `Docs & Governance`: `16`
- `Backlog Cleanup`: `3`

Assigned by target milestone:
- `M2`: `5`
- `M3`: `3`
- `M4`: `1`
- `M5`: `7`
- `M7`: `7`
- `M8`: `1`
- `M10`: `5`
- `M11`: `3`
- `M12`: `11`
- `M13`: `8`
- `M14`: `4`
- `M15`: `1`
- `M16`: `1`
- `M17`: `12`
- `M18`: `7`
- `M19`: `35`
- `M20`: `3`
- `M21`: `3`
- `M22`: `21`
- `M23`: `14`
- `M24`: `22`
- `M25`: `2`
- `M26`: `9`
- `M28`: `9`
- `M29`: `21`
- `M30`: `3`
- `M34`: `8`
- `M0 - Triage` (ambiguous fallback): `37`

## Ambiguous PRs (assigned to M0 - Triage)
`10, 13, 14, 15, 31, 48, 50, 54, 60, 63, 73, 74, 78, 101, 102, 103, 105, 106, 109, 110, 111, 112, 116, 120, 126, 127, 134, 136, 139, 156, 162, 217, 220, 221, 227, 260, 265`

## Catch-all Milestone Cleanup
First apply pass:
- `Docs & Governance`: deleted (empty)
- `Infra & Tooling`: retained (non-empty at that moment)
- `Backlog Cleanup`: retained (non-empty at that moment)

Second apply pass (idempotent reconciliation):
- `Infra & Tooling`: deleted
- `Backlog Cleanup`: deleted
- `Docs & Governance`: already missing

## Final Verification
`--verify` result after apply cleanup:
- `missing_milestone_count: 0`
- `catchall_milestone_count: 0`
- `nonroadmap_milestone_count: 0`
- Status: `MILESTONE_REHOME_VERIFY_OK`
