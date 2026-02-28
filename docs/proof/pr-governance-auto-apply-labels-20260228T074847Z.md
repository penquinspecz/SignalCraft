# PR Governance Auto-Apply Labels Proof (2026-02-28)

## Scope
Add deterministic automation that applies governance labels on PR metadata/content changes without checking out PR code.

## Files Changed
- `.github/workflows/pr-governance-apply.yml`

## Trigger + Safety
- Trigger: `pull_request` on `opened`, `reopened`, `synchronize`, `edited`, `ready_for_review`
- No checkout of PR head
- Uses GitHub API only via `actions/github-script`
- Permissions: `contents: read`, `pull-requests: write`, `issues: write`

## Deterministic Rules
1. Provenance (exactly one)
- `codex/*` -> `from-codex`
- `composer/*` -> `from-composer`
- otherwise -> `from-human`

2. Type (exactly one)
- docs-only (`docs/**` or README paths) OR title starts `docs(` / `docs:` -> `type:docs`
- title starts `fix(` / `fix:` -> `type:fix`
- title starts `feat(` / `feat:` -> `type:feat`
- otherwise -> `type:chore`

3. Area (at least one)
- `docs/**` or README -> `area:docs`
- `src/ji_engine/**` or `src/jobintel/**` -> `area:engine`
- `src/ji_engine/providers/**` -> `area:providers`
- `scripts/ops/**` or `ops/**` -> `area:dr`
- `ops/aws/**` or `ops/k8s/**` -> `area:infra`
- fallback -> `area:unknown`

## Proof Cases
- Open PR: workflow runs on `opened` and applies missing `from-*`, `type:*`, and inferred `area:*` labels.
- Edit title: workflow runs on `edited`; selected `type:*` label is recomputed and conflicting `type:*` labels are replaced.
- Push commits: workflow runs on `synchronize`; inferred `area:*` labels are recomputed and ensured present while provenance/type remain normalized.

## Notes
- Milestones are intentionally not auto-set by this workflow.
- Required governance labels are auto-created if missing, with stable color/description values.
