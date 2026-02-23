# SignalCraft Versioning & Releases

SignalCraft uses **two parallel release tracks**:

1. **Product versions** (Semantic Versioning): `vMAJOR.MINOR.PATCH`
2. **Operational milestone releases** (timestamped): `mNN-YYYYMMDDTHHMMSSZ`

This is intentional: SignalCraft is both a deterministic engine *and* an operable system.

---

## 1) Product Versions (SemVer)

**Tags:** `v0.2.0`, `v0.2.1`, ...

Use product versions when changes affect:

- Deterministic pipeline behavior (outputs, ordering, scoring)
- Provider schema or ingestion semantics
- Snapshot/replay contracts
- Public artifacts (JSON/CSV/MD) formats or semantics
- Canonical operator UX: entrypoints, runbooks, primary workflows
- Security/guardrail contracts that users/operators rely on

### SemVer rules

#### MAJOR (v1.0.0 → v2.0.0)
Increment when you introduce breaking changes to:
- output schema/format
- provider schema
- replay/snapshot contract
- CLI/entrypoint contracts
- deployment manifests contracts

#### MINOR (v0.2.0 → v0.3.0)
Increment when you add capability without breaking contracts:
- new providers
- new scoring features behind defaults
- new deterministic receipts/artifacts
- new deploy surfaces that don't break existing ones

#### PATCH (v0.2.0 → v0.2.1)
Increment when you fix behavior without changing contracts:
- bug fixes
- reliability improvements
- doc/runbook fixes
- CI hardening

---

## 2) Operational Milestone Releases (timestamped)

**Tags:** `m19-20260222T201429Z`

These releases are audit-first and are used to anchor operational proof:
- DR drills + receipts
- release image digests + architecture verification
- infra automation changes
- cost discipline guardrails

### Required release body fields (milestone releases)

Each milestone release must include:

- `[from-composer]` marker when created via Cursor Composer
- `main HEAD` SHA
- `IMAGE_REF` (digest pinned)
- Architectures verified (amd64, arm64 as applicable)
- PRs included
- Receipt paths for build/verify/drill proofs
- Release proof bundle: `ops/proof/releases/release-<tag>.json` or CI artifact `release-metadata-<tag>` (includes `ci_run_url` for multi-arch gate evidence)
- High-level "Operational Impact" summary (bullet list)

---

## 3) Release Cadence

- **Milestone releases**: as needed to anchor proof (e.g., DR hardening, infra workflow improvements).
- **Product versions**: cut at milestone boundaries when a user-facing capability is complete and stable.
- No release is considered valid unless the deterministic gates and policy checks pass.

---

## 4) Proof Requirements (minimum)

Before tagging either release type:

- `./scripts/audit_determinism.sh` PASS
- `python3 scripts/ops/check_dr_guardrails.py` PASS
- `python3 scripts/ops/check_dr_docs.py` PASS
- Terraform validate for DR modules (with `-backend=false`) PASS
- Secret scan (gitleaks) PASS when available
- For milestone releases: at least one DR proof run (bounded/cost-disciplined) with teardown verification

---

## 5) Naming Conventions

### Milestone tags
- Format: `mNN-YYYYMMDDTHHMMSSZ` (UTC)
- Title format:
  - `SignalCraft MNN — <theme>`
  - Example: `SignalCraft M19 — DR Hardening + Cost Discipline`

### Product tags
- Format: `vMAJOR.MINOR.PATCH`
- Title format:
  - `SignalCraft vX.Y.Z — <theme>`
  - Example: `SignalCraft v0.2.0 — Deterministic Releases + DR-Proven Operator Workflow`

---

## 6) Release Notes Generator

`scripts/release/render_release_notes.py` produces deterministic release body markdown from the required fields. Use it to generate GitHub release notes that conform to `docs/RELEASE_TEMPLATE.md`. Set `FROM_COMPOSER=1` to include the `[from-composer]` marker.
