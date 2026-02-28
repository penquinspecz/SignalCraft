# release-ecr tier enforcement proof (20260228T032512Z)

## Scope
Implemented explicit release template mode enforcement in `.github/workflows/release-ecr.yml` and updated renderer/validator interfaces so product `major` releases require major-only sections.

## Changes
- Added workflow_dispatch inputs:
  - `release_kind` (`product|milestone`)
  - `release_tier` (`major|minor|patch`)
  - `major` (boolean override to force major enforcement)
- Added tag trigger handling (`v*`, `m*`) and mode inference logic:
  - `vX.Y.Z` => product
  - tier inferred from previous product tag by semver delta (major/minor/patch)
  - `mNN-...` => milestone
- Added pre-publish gate in `release-ecr`:
  - Render notes with `scripts/release/render_release_notes.py --release-tier ...`
  - Validate with `scripts/release/validate_release_body.py` before ECR publish step
- Extended renderer interface:
  - new `--release-tier major|minor|patch`
  - major-only sections emitted when tier=`major`:
    - `Why this release exists`
    - `Migration / Upgrade Guide`
    - `Compatibility Matrix`
    - `Deprecations Timeline`
- Added validator interface + enforcement:
  - `--release-kind`
  - `--release-tier`
  - checks required heading set by mode
  - rejects placeholders (`TODO`, `TBD`, `fill in`)
  - requires digest-pinned IMAGE_REF in body

## Local validation commands
- `python3 scripts/release/render_release_notes.py --release-kind product --release-tier minor --tag v0.2.1 --image-ref 000000000000.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:0000000000000000000000000000000000000000000000000000000000000000 --out /tmp/release-minor.md`
- `python3 scripts/release/validate_release_body.py --release-kind product --release-tier minor --body-file /tmp/release-minor.md`
- `python3 scripts/release/render_release_notes.py --release-kind product --release-tier major --tag v1.0.0 --image-ref 000000000000.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:0000000000000000000000000000000000000000000000000000000000000000 --out /tmp/release-major.md`
- `python3 scripts/release/validate_release_body.py --release-kind product --release-tier major --body-file /tmp/release-major.md`
- `python3 scripts/release/render_release_notes.py --release-kind milestone --tag m19-20260228T000000Z --image-ref 000000000000.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:0000000000000000000000000000000000000000000000000000000000000000 --out /tmp/release-milestone.md`
- `python3 scripts/release/validate_release_body.py --release-kind milestone --release-tier patch --body-file /tmp/release-milestone.md`

Validation result:
- PASS: release body validated for kind=product tier=minor
- PASS: release body validated for kind=product tier=major
- PASS: release body validated for kind=milestone tier=patch

## Source commit
- Base HEAD during change: `5b8cffaf36f0b3ee03638d9542b54da5ed65b86d`
