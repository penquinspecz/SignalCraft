© 2026 Chris Menendez. Source Available — All Rights Reserved.
See LICENSE for permitted use.

# AI Workflow

This document records planner/execution conventions for AI-assisted delivery.

## Planner Transition

- Planner transition date: **2026-03-01**
- Planner transition: **ChatGPT -> Claude**
- Scope: planning/default planning recommendations for new work starting on and
  after the transition date.

## Labeling Guidance

- Going forward, optional planner provenance labels may include:
  - `planner:claude`
- Do **not** backfill historical PRs with planner labels retroactively.
- Existing required PR governance labels (provenance/type/area + milestone)
  remain unchanged and enforced by repository governance workflows.

## Notes

- This workflow note is additive and does not alter determinism/replay
  contracts.
- Planner choice does not change artifact schema contracts or gate requirements.
