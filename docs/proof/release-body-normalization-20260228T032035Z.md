# Release Body Normalization Proof (20260228T032035Z)

## Scope
Metadata-only release-body normalization to the canonical in-body templates.

Target releases updated:
- `v0.1.0`
- `m19-20260222T181245Z`
- `m19-20260222T201429Z`
- `v0.2.0`

## Before/After Summary

### v0.1.0
- Before: historical narrative + long PR list; no explicit in-body operator proof sections.
- After: canonical product sections (`Highlights`, `What's Proven (Operator Reality Check)`, `Images (Digest-pinned)`, `Upgrade / Operational Notes`, `Changes (categorized)`, `Breaking Changes`, `Known Issues`, `Proof References`, `Integrity`).
- Legacy evidence handling: includes `Not recorded at tag time` and `CI-backed release proof enforcement not implemented at that tag.`

### m19-20260222T181245Z
- Before: mixed milestone summary with external `/tmp` receipt references.
- After: canonical milestone sections (`Milestone Context`, `What was exercised`, `Execution Evidence`, `Images (Digest-pinned)`, `Guardrails/Determinism checks`, `Outcome + Next steps`, `Proof References`).
- Legacy evidence handling: CI enforcement note + explicit `Not recorded at tag time` for missing execution fields.

### m19-20260222T201429Z
- Before: mixed milestone summary with external `/tmp` receipt references.
- After: canonical milestone structure as above.
- Legacy evidence handling: CI enforcement note + explicit `Not recorded at tag time` for missing execution fields.

### v0.2.0
- Before: mixed product narrative with non-canonical heading set.
- After: canonical product structure with digest-pinned image and integrity footer containing CI workflow/id/url.
- CI evidence in body:
  - workflow: `release-ecr`
  - run id: `22511541023`
  - url: `https://github.com/penquinspecz/SignalCraft/actions/runs/22511541023`

## Validation Results
Post-update release bodies validated using `scripts/release/validate_release_body.py`:
- `v0.1.0` (product minor): PASS with `--dev-mode` (legacy no digest at tag time)
- `m19-20260222T181245Z` (milestone): PASS
- `m19-20260222T201429Z` (milestone): PASS
- `v0.2.0` (product minor): PASS with `--require-ci-evidence`

## Tag SHA Integrity (unchanged)
- `v0.1.0` = `52a18ff9f0006de6e3d679373c26e630bfde790c`
- `m19-20260222T181245Z` = `5b536824d1bec7969f5acbcc31f27a2a65732707`
- `m19-20260222T201429Z` = `3a1b0a8cc8da9b7525446d16afc5ee814b1b3d53`
- `v0.2.0` = `5b8cffaf36f0b3ee03638d9542b54da5ed65b86d`

Confirmation: no tag objects were moved, deleted, or recreated.

## Release Ordering
`gh release list` ordering remained unchanged:
1. `v0.2.0`
2. `m19-20260222T201429Z`
3. `m19-20260222T181245Z`
4. `v0.1.0`

## Command Log
- Captured pre-update bodies:
  - `gh release view <tag> --repo penquinspecz/SignalCraft --json body --jq .body > .tmp/release-before/<tag>.md`
- Generated normalized bodies:
  - `python3 /Users/chris.menendez/Projects/signalcraft/.tmp-clone-release-body-policy/scripts/release/render_release_notes.py ... --out .tmp/release-bodies/<tag>.md`
- Pre-apply validation:
  - `python3 /Users/chris.menendez/Projects/signalcraft/.tmp-clone-release-body-policy/scripts/release/validate_release_body.py ...`
- Applied metadata updates:
  - `gh release edit <tag> --repo penquinspecz/SignalCraft --notes-file .tmp/release-bodies/<tag>.md`
- Captured post-update bodies:
  - `gh release view <tag> --repo penquinspecz/SignalCraft --json body --jq .body > .tmp/release-after/<tag>.md`
- Post-apply validation:
  - `python3 /Users/chris.menendez/Projects/signalcraft/.tmp-clone-release-body-policy/scripts/release/validate_release_body.py ...`
- Tag SHA compare:
  - `git rev-list -n 1 <tag>` before/after and `diff -u`
