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
- [ ] docs
- [ ] other

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

**from-composer** is tracked via label, not PR title. Do not put `[from-composer]` in the PR title.
