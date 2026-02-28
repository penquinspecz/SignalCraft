# Label Taxonomy

SignalCraft uses labels for PR governance: provenance, type, and area. **CI enforces** these rules via `.github/workflows/pr-governance.yml`.

## Taxonomy

| Category | Purpose | Examples |
|----------|---------|----------|
| **Provenance** | Origin of changes | `from-composer`, `from-codex`, `from-human` |
| **Type** | Kind of change | `type:feat`, `type:fix`, `type:chore`, `type:docs`, `type:refactor`, `type:test` |
| **Area** | Domain touched | `area:engine`, `area:providers`, `area:dr`, `area:release`, `area:infra`, `area:docs` (docs-only), `area:unknown` (fallback) |

## Type vs Area

- `type:*` describes the kind of change (for example: bug fix vs docs vs feature).
- `area:*` describes which subsystem is touched (for example: engine, providers, infra, dr, docs).
- Docs PRs should carry both `type:docs` and `area:docs`.

## Required Labels for Merge (Enforced by CI)

- **Exactly one provenance label:** `from-composer`, `from-codex`, or `from-human`
- **Exactly one type:*** label: feat, fix, chore, docs, refactor, test
- **At least one area:*** label: engine, providers, dr, release, infra, docs (docs-only), or unknown (fallback)
- **Milestone required:** Any milestone (roadmap or bucket: Infra & Tooling, Docs & Governance, Backlog Cleanup)

**Provenance is label-only.** PR titles must NOT contain `[from-composer]`, `[from-codex]`, or `[from-human]`. Every PR must have exactly one provenance label; pick based on who authored the changes (Composer / Codex / human).

See `docs/RELEASE_PROCESS.md` for the Milestone B rule and bucket milestones.

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

The `.github/workflows/labeler.yml` workflow normalizes governance labels deterministically:

- Exactly one provenance label based on branch prefix:
  - `composer/*` -> `from-composer`
  - `codex/*` -> `from-codex`
  - everything else -> `from-human`
- Exactly one type label with priority:
  - docs-only (`docs/**` and/or `README*`) or title starts with `docs(` / `docs:` -> `type:docs`
  - title starts with `fix(` / `fix:` -> `type:fix`
  - title starts with `feat(` / `feat:` -> `type:feat`
  - fallback -> `type:chore`
- Area labels are inferred from changed paths (see `.github/labeler.yml`) and normalized to keep docs/fallback semantics valid.

- `area:docs` is removed for mixed-domain PRs when another specific area exists.
- `area:unknown` is fallback-only and removed when a specific area exists.

You can simulate the same decision logic locally:

```bash
python scripts/dev/simulate_pr_labeler.py \
  --title "fix(engine): harden resolver" \
  --head-ref "codex/security-fix" \
  --changed-file src/ji_engine/utils/network_shield.py
```
