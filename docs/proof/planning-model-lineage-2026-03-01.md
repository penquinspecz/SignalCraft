# Planning Model Lineage Proof (2026-03-01)

## Scope
Additive documentation-only update to record roadmap planning model lineage and planner cutover policy.

## Files Updated
- `docs/ROADMAP.md`
  - added `Product Thesis (2026)` section emphasizing temporal intelligence and provider onboarding factory continuity
  - added `Planning Model Lineage` section documenting planner cutover semantics without retroactive PR relabeling
- `docs/AI_WORKFLOW.md`
  - added planner transition record (`ChatGPT -> Claude`, effective 2026-03-01)
  - documented optional `planner:claude` usage going forward (no backfill)

## Validation
- `make format` PASS
- `make lint` PASS
- `make ci-fast` PASS
- `make gate` PASS

## Contract Notes
- Determinism unchanged.
- Replay unchanged.
- Snapshot baseline unchanged.
