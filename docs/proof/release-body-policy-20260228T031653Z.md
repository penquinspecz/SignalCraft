# Release Body Policy Proof (20260228T031653Z)

## Goal
Make release bodies self-contained and auditable with lightweight CI enforcement, without changing tag history.

## What changed
- Added SemVer + release-body policy updates in `docs/VERSIONING.md`:
  - explicit MAJOR/MINOR/PATCH rules
  - explicit examples from this repo (IAM least-privilege fix => patch, DR success-path proven => minor, schema break => major)
  - digest-pinned IMAGE_REF requirement for non-dev releases
  - milestone tags as operational proof points, not product promises
- Added canonical templates:
  - `docs/RELEASE_TEMPLATE_PRODUCT.md`
  - `docs/RELEASE_TEMPLATE_MILESTONE.md`
- Updated `docs/RELEASE_TEMPLATE.md` to point to canonical templates.
- Updated `docs/RELEASE_NOTES_STYLE.md` to align with required heading sets.
- Updated `docs/RELEASE_PROCESS.md` with canonical flow:
  1) `release-ecr` metadata/proof
  2) renderer output
  3) validator gate
  4) publish
  - plus MAJOR-only section requirements.
- Reworked renderer `scripts/release/render_release_notes.py`:
  - product (major vs minor/patch) heading sets
  - milestone heading set
  - explicit `None` defaults (no placeholder text)
  - digest + CI integrity footer
  - IMAGE_REF fallback line `Not recorded at tag time` when unavailable
- Added validator `scripts/release/validate_release_body.py`:
  - enforces heading set for product major vs product minor/patch vs milestone
  - requires digest-pinned IMAGE_REF unless explicit DEV_MODE override
  - rejects placeholder text (`TODO`, `TBD`, `fill in`)
  - optional `--require-ci-evidence` enforces `CI workflow`, `CI run ID`, `CI workflow URL`
- Added smoke validation script `scripts/release/smoke_validate_release_body.sh` with required scenarios:
  - pass: product minor
  - fail: missing digest-pinned IMAGE_REF
  - pass: milestone
  - fail: product major missing Migration / Upgrade Guide
- Added unit-ish pytest coverage file `tests/test_validate_release_body.py` for the same scenarios.
- Updated `.github/workflows/release-ecr.yml`:
  - optional `workflow_dispatch` release publish inputs (`publish_release`, `release_kind`, `semver_level`, `release_body`, etc.)
  - pre-publish validator step
  - publish step runs only after validation passes

## Local validation run
- `python3 -m py_compile scripts/release/render_release_notes.py scripts/release/validate_release_body.py` => PASS
- `scripts/release/smoke_validate_release_body.sh` => PASS
- `python3 scripts/ops/check_dr_docs.py` => PASS
- `python3 scripts/ops/check_dr_guardrails.py` => PASS
- `./scripts/audit_determinism.sh` => PASS
- `python3 -m pytest -q tests/test_validate_release_body.py` => BLOCKED locally (`pytest` module unavailable)
- `make lint` => BLOCKED locally (Xcode license not accepted in this environment)

## Determinism and history safety
- No tag objects changed.
- No history rewrite performed.
- Policy relies on render+validate before publish.
