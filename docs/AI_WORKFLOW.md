© 2026 Chris Menendez. Source Available — All Rights Reserved.
See LICENSE for permitted use.

# AI Workflow

This document records planner/execution conventions for AI-assisted delivery.

## Planner Transition

- Transition date: **2026-03-01**
- Planner transition: **ChatGPT -> Claude**
- Scope: roadmap planning/model-lineage guidance for work planned on or after
  the transition date.

## Label Guidance

- Going forward, optional planner metadata may use:
  - `planner:claude`
- Do **not** backfill historical PRs with planner labels.
- Required governance labels remain unchanged:
  - exactly one `from-*`
  - exactly one `type:*`
  - at least one `area:*`
  - milestone required

## Notes

- Planner lineage is documentation metadata, not execution behavior.
- Determinism/replay/snapshot contracts are unchanged by planner choice.
