## Branch

Ensure branch is deletable; do not use permanent branch names. Head branches are auto-deleted after merge.

## Type

- [ ] feat
- [ ] fix
- [ ] chore
- [ ] docs
- [ ] refactor
- [ ] test

## Area

- [ ] engine
- [ ] providers
- [ ] dr
- [ ] release
- [ ] infra
- [ ] docs (docs-only PRs)
- [ ] unknown (fallback only when no specific area applies)

`area:docs` is not a default label. Use it only for docs-only changes.

## Milestone

**Required** unless this PR uses a bucket milestone: **Infra & Tooling** / **Docs & Governance** / **Backlog Cleanup**.

- [ ] Roadmap milestone (e.g. M19, M20)
- [ ] Bucket milestone: Infra & Tooling
- [ ] Bucket milestone: Docs & Governance
- [ ] Bucket milestone: Backlog Cleanup
- [ ] N/A (explain in description)

## Determinism / Guardrails Impact

- [ ] No nondeterministic behavior introduced
- [ ] No contract-surface changes without schema/versioning
- [ ] Replay and snapshot checks unaffected (or explicitly updated)

## Validation Checklist

- [ ] `./scripts/audit_determinism.sh` passes
- [ ] `python3 scripts/ops/check_dr_docs.py` passes (if DR-related)
- [ ] `python3 scripts/ops/check_dr_guardrails.py` passes (if DR-related)
- [ ] `terraform validate` (if Terraform files changed)
- [ ] Secret scan reminder: no credentials or secrets in diff
- [ ] Working tree clean before push

## Provenance

**Provenance is labels only (never in title).** Every PR must have exactly one provenance label. Pick based on who authored the changes: `from-composer` (Composer), `from-codex` (Codex), or `from-human` (human). Do not put `[from-composer]`, `[from-codex]`, or `[from-human]` in the PR title.
