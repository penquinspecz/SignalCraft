# Area Label Policy Fix Proof

## Scope
Fix systemic `area:docs` over-labeling on PRs while keeping governance strict and actionable.

## Root Cause
`area:docs` was auto-applied by `.github/labeler.yml` on **any** `docs/**` change (`any-glob-to-any-file`).
Because most DR/infra/release PRs include proof docs under `docs/proof/**`, mixed-domain PRs were frequently labeled `area:docs`, polluting triage.

## Fix Implemented
1. **Docs label is now docs-only**
   - Changed `.github/labeler.yml` for `area:docs` from `any-glob-to-any-file` to `any-glob-to-all-files` on `docs/**`.
2. **Fallback area policy in automation**
   - Updated `.github/workflows/labeler.yml` to:
     - remove `area:docs` when another specific `area:*` exists,
     - auto-apply `area:unknown` when no area can be inferred,
     - remove `area:unknown` once a specific area label exists,
     - fail with an actionable message if `area:unknown` cannot be applied.
3. **Governance enforcement tightened**
   - Updated `.github/workflows/pr-governance.yml` to fail when:
     - `area:docs` is used alongside another specific area (docs fallback misuse),
     - `area:unknown` is kept alongside specific areas.
4. **Policy docs/templates updated**
   - Updated `docs/LABELS.md`, `.github/pull_request_template.md`, and `CONTRIBUTING.md` with explicit rules:
     - at least one `area:*` required,
     - `area:docs` is docs-only,
     - `area:unknown` is fallback-only.

## PR Script Audit
Searched for hardcoded `area:docs` in PR command snippets/scripts and found none requiring code changes:

```bash
rg -n "gh pr (create|edit).*area:docs|--label\\s+area:docs|labels?:\\s*\\[.*area:docs" scripts .github docs -g '!docs/proof/**'
```

## Validation
- `./scripts/audit_determinism.sh`
- `python3 scripts/ops/check_dr_docs.py`
- `python3 scripts/ops/check_dr_guardrails.py`

## Baseline
- `origin/main` SHA at change start: `af1040cb8e730bd8674e3e1a894f0acf9da4e8e4`
