# Label Taxonomy

SignalCraft uses labels for PR governance: provenance, type, and area. **CI enforces** these rules via `.github/workflows/pr-governance.yml`.

## Taxonomy

| Category | Purpose | Examples |
|----------|---------|----------|
| **Provenance** | Origin of changes | `from-composer`, `from-codex`, `from-human` |
| **Type** | Kind of change | `type:feat`, `type:fix`, `type:chore`, `type:docs`, `type:refactor`, `type:test` |
| **Area** | Domain touched | `area:engine`, `area:providers`, `area:dr`, `area:release`, `area:infra`, `area:docs` (docs-only), `area:unknown` (fallback) |

## Required Labels for Merge (Enforced by CI)

- **Exactly one provenance label:** `from-composer`, `from-codex`, or `from-human`
- **Exactly one type:*** label: feat, fix, chore, docs, refactor, test
- **At least one area:*** label: engine, providers, dr, release, infra, docs (docs-only), or unknown (fallback)
- **Milestone required:** Any milestone (roadmap or bucket: Infra & Tooling, Docs & Governance, Backlog Cleanup)

**Provenance is label-only.** PR titles must NOT contain `[from-composer]`, `[from-codex]`, or `[from-human]`. Every PR must have exactly one provenance label; pick based on who authored the changes (Composer / Codex / human).

See `docs/RELEASE_PROCESS.md` for the Milestone B rule and bucket milestones.

## Milestone Metadata Sync

PR governance requires a GitHub milestone (roadmap or bucket) on every PR.
To align GitHub milestones with `docs/ROADMAP.md`, run:

```bash
make milestones-sync
```

Default behavior parses `## Milestone <number>` headings and ensures matching
`M<number>` milestones exist, then ensures bucket milestones also exist:
`Infra & Tooling`, `Docs & Governance`, and `Backlog Cleanup`.

For roadmap headings with suffixes (for example `Milestone 19A/19B/19C`), sync
maps them deterministically to the base numeric milestone (`M19`).

## Examples

### from-composer PR (docs-only)

- **Labels:** `type:docs`, `area:docs`, `from-composer`
- **Milestone:** Docs & Governance (bucket)
- **Title:** `chore(governance): PR template + milestone policy (B)` — no `[from-composer]` in title

### from-codex PR (DR fix)

- **Labels:** `type:fix`, `area:dr`, `from-codex`
- **Milestone:** Infra & Tooling (bucket)
- **Title:** `fix(dr): correct terraform variable` — no `[from-codex]` in title

### Normal PR (human-authored)

- **Labels:** `type:feat`, `area:engine`, `from-human`
- **Milestone:** M19 (roadmap)
- **Title:** `feat(engine): add snapshot immutability check`

## Auto-Labeling

The `.github/workflows/labeler.yml` workflow adds `area:*` labels based on changed paths (see `.github/labeler.yml`) with these rules:

- `area:docs` is auto-applied only when all changed files are in `docs/**` (docs-only PRs).
- For mixed-domain PRs, automation removes `area:docs` when another specific area exists.
- If no specific `area:*` can be inferred, automation applies `area:unknown` as fallback.
