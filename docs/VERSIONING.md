# SignalCraft Versioning & Releases

SignalCraft has two release tracks:

1. Product releases: `vMAJOR.MINOR.PATCH`
2. Operational milestone releases: `mNN-YYYYMMDDTHHMMSSZ`

Product releases are customer/operator promises. Milestone releases are operational proof points.

## Product SemVer policy

### MAJOR
Use MAJOR when you introduce a breaking contract change.

Examples:
- artifact schema changes that break existing readers
- replay/snapshot contract changes
- CLI or config behavior changes that require migration

Explicit repo example:
- Config schema contract change (`schemas/*.schema.v*.json`) is MAJOR.

### MINOR
Use MINOR when you add meaningful capability without breaking existing contracts.

Examples:
- new deterministic DR workflow capability proven end-to-end
- new non-breaking provider capability
- new operational path available behind existing contracts

Explicit repo example:
- DR workflow proven through manual approval gate (M19B) maps to MINOR product capability maturity.

### PATCH
Use PATCH for fixes/hardening without contract changes.

Examples:
- bug fixes
- least-privilege IAM permission adjustments
- workflow reliability and docs corrections

Explicit repo example:
- IAM least-privilege unblock loop (`iam:ListRolePolicies`, `iam:ListAttachedRolePolicies`, etc.) maps to PATCH.

## IMAGE_REF policy

- Non-dev product and milestone releases must include digest-pinned `IMAGE_REF`:
  - `<account>.dkr.ecr.<region>.amazonaws.com/<repo>@sha256:<64-hex>`
- Floating tags (including `:latest`) are not allowed for release notes.
- Dev-only exceptions are allowed only with explicit `DEV_MODE` override in validation tooling.

## Milestone tags vs product tags

- Milestone tags (`mNN-*`) capture operational evidence at a point in time.
- Milestone tags do not imply product compatibility promises.
- Product tags (`vX.Y.Z`) are the compatibility and upgrade contract.
- A product release may summarize one or more prior milestone proof points.

## Minimum release proof requirements

Before publishing any release:

- `./scripts/audit_determinism.sh` PASS
- `python3 scripts/ops/check_dr_docs.py` PASS
- `python3 scripts/ops/check_dr_guardrails.py` PASS
- release metadata proof bundle validated:
  - `python3 scripts/release/check_release_proof_bundle.py <metadata_path> --require-ci-evidence`

## Canonical release-body templates

- Product: `docs/RELEASE_TEMPLATE_PRODUCT.md`
- Milestone: `docs/RELEASE_TEMPLATE_MILESTONE.md`

Renderer and validator:

- render: `scripts/release/render_release_notes.py`
- validate: `scripts/release/validate_release_body.py`
