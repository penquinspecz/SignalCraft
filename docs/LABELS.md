# Label Taxonomy

SignalCraft uses labels for PR governance: provenance, type, and area. **CI enforces** these rules via `.github/workflows/pr-governance.yml`.

## Taxonomy

| Category | Purpose | Examples |
|----------|---------|----------|
| **Provenance** | Origin of changes | `from-composer`, `from-codex`, `from-human` |
| **Type** | Kind of change | `type:feat`, `type:fix`, `type:chore`, `type:docs`, `type:refactor`, `type:test` |
| **Area** | Domain touched | `area:engine`, `area:providers`, `area:dr`, `area:release`, `area:infra`, `area:docs` |

## Required Labels for Merge (Enforced by CI)

- **Exactly one provenance label:** `from-composer`, `from-codex`, or `from-human`
- **Exactly one type:*** label: feat, fix, chore, docs, refactor, test
- **Exactly one area:*** label: engine, providers, dr, release, infra, docs
- **Milestone required:** Any milestone (roadmap or bucket: Infra & Tooling, Docs & Governance, Backlog Cleanup)

**Provenance is label-only.** PR titles must NOT contain `[from-composer]`, `[from-codex]`, or `[from-human]`.

See `docs/RELEASE_PROCESS.md` for the Milestone B rule and bucket milestones.

## Examples

### from-composer PR (docs)

- **Labels:** `type:docs`, `area:docs`, `from-composer`
- **Milestone:** Docs & Governance (bucket)
- **Title:** `chore(governance): PR template + milestone policy (B)` — no `[from-composer]` in title

### Normal PR (human-authored)

- **Labels:** `type:feat`, `area:engine`, `from-human`
- **Milestone:** M19 (roadmap)
- **Title:** `feat(engine): add snapshot immutability check`

## Auto-Labeling

The `.github/workflows/labeler.yml` workflow adds `area:*` labels based on changed paths (see `.github/labeler.yml`). Authors may need to remove extra area labels if a PR touches multiple domains.
