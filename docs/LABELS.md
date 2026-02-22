# Label Taxonomy

SignalCraft uses labels for PR governance: provenance, type, and area.

## Taxonomy

| Category | Purpose | Examples |
|----------|---------|----------|
| **Provenance** | Origin of changes | `from-composer`, `from-codex` |
| **Type** | Kind of change | `type:feat`, `type:fix`, `type:chore`, `type:docs`, `type:refactor`, `type:test` |
| **Area** | Domain touched | `area:engine`, `area:providers`, `area:dr`, `area:release`, `area:infra`, `area:docs`, `area:other` |

## Required Labels for Merge

- **type:*** — One of feat, fix, chore, docs, refactor, test
- **area:*** — One of engine, providers, dr, release, infra, docs, other
- **from-composer** — Required when the PR was authored via Composer (provenance label)

See `docs/RELEASE_PROCESS.md` for the Milestone B rule and bucket milestones.

## Examples

### from-composer PR (docs)

- **Labels:** `type:docs`, `area:docs`, `from-composer`
- **Milestone:** Docs & Governance (bucket)
- **Title:** `chore(governance): PR template + milestone policy (B)` — no `[from-composer]` in title

### Normal PR (human-authored)

- **Labels:** `type:feat`, `area:engine`
- **Milestone:** M19 (roadmap)
- **Title:** `feat(engine): add snapshot immutability check`
