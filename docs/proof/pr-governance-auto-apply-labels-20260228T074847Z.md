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
- docs-only (`docs/**` or README paths only) -> `area:docs`
- `src/ji_engine/**` or `src/jobintel/**` -> `area:engine`
- `src/ji_engine/providers/**` -> `area:providers`
- `scripts/ops/**` or `ops/**` -> `area:dr`
- `ops/aws/**` or `ops/k8s/**` -> `area:infra`
- `.github/**`, `scripts/dev/**`, `scripts/**` (non-ops), `scripts/release/**`, `scripts/security_*`, `Makefile` -> `area:infra`
- fallback -> `area:unknown`

## Proof Cases
- Open PR: workflow runs on `opened` and applies missing `from-*`, `type:*`, and inferred `area:*` labels.
- Edit title: workflow runs on `edited`; selected `type:*` label is recomputed and conflicting `type:*` labels are replaced.
- Push commits: workflow runs on `synchronize`; inferred `area:*` labels are recomputed and ensured present while provenance/type remain normalized.
- `.github/workflows/*`-only PR resolves to `area:infra` (not `area:unknown`) with one provenance and one type label.
- PR without milestone: workflow defaults milestone to `Backlog Cleanup` when present; otherwise `Infra & Tooling` when present.

## Notes
- Existing milestone is never overridden by the auto-apply workflow.
- If neither default bucket milestone exists, milestone remains unset and strict `pr-governance` enforcement still fails closed.
- Required governance labels are auto-created if missing, with stable color/description values.
