#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VALIDATOR="$ROOT_DIR/scripts/release/validate_release_body.py"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

run_expect_pass() {
  local body_file="$1"
  shift
  python3 "$VALIDATOR" --body-file "$body_file" "$@" >/dev/null
}

run_expect_fail() {
  local body_file="$1"
  shift
  if python3 "$VALIDATOR" --body-file "$body_file" "$@" >/dev/null 2>&1; then
    echo "expected validation failure but command succeeded: $*" >&2
    exit 1
  fi
}

cat >"$TMP_DIR/product-minor.md" <<'MD'
# SignalCraft Product Release v0.2.1

## Highlights
- Deterministic release-note rendering.

## What's Proven (Operator Reality Check)
- Validator enforces required sections.

## Images (Digest-pinned)
- IMAGE_REF: `123456789012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
- Digest: `sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`

## Upgrade / Operational Notes
- None

## Changes (categorized)
- Added:
  - Release-body validation.
- Changed:
  - None
- Fixed:
  - None

## Breaking Changes
- None

## Known Issues
- None

## Proof References
- docs/proof/example.md

## Integrity
- Main commit SHA: `1111111111111111111111111111111111111111`
- IMAGE_REF digest: `sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
- CI workflow URL: `https://github.com/penquinspecz/SignalCraft/actions/runs/123`
- CI run ID: `123`
- CI workflow: `release-ecr`
MD

cat >"$TMP_DIR/product-missing-digest.md" <<'MD'
# SignalCraft Product Release v0.2.1

## Highlights
- None

## What's Proven (Operator Reality Check)
- None

## Images (Digest-pinned)
- IMAGE_REF: `123456789012.dkr.ecr.us-east-1.amazonaws.com/jobintel:latest`
- Digest: Not recorded at tag time

## Upgrade / Operational Notes
- None

## Changes (categorized)
- Added:
  - None
- Changed:
  - None
- Fixed:
  - None

## Breaking Changes
- None

## Known Issues
- None

## Proof References
- docs/proof/example.md

## Integrity
- Main commit SHA: `1111111111111111111111111111111111111111`
- IMAGE_REF digest: Not recorded at tag time
- CI workflow URL: `https://github.com/penquinspecz/SignalCraft/actions/runs/123`
- CI run ID: `123`
- CI workflow: `release-ecr`
MD

cat >"$TMP_DIR/milestone-pass.md" <<'MD'
# SignalCraft Milestone Release m19-20260222T201429Z

## Milestone Context
- milestone_tag: `m19-20260222T201429Z`
- Main commit SHA: `2222222222222222222222222222222222222222`
- intent: DR rehearsal evidence

## What was exercised
- success path through request_manual_approval

## Execution Evidence
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19`
- terminal_state: `RequestManualApproval`
- terminal_status: `ABORTED`
- receipts_root: `docs/proof/receipts-m19/`

## Images (Digest-pinned)
- IMAGE_REF: `123456789012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb`
- Digest: `sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb`

## Guardrails/Determinism checks
- ./scripts/audit_determinism.sh: PASS

## Outcome + Next steps
- outcome: success path proven
- next_step: none

## Proof References
- docs/proof/m19.md
MD

cat >"$TMP_DIR/product-major-missing-migration.md" <<'MD'
# SignalCraft Product Release v1.0.0

## Highlights
- Major contract boundary.

## What's Proven (Operator Reality Check)
- None

## Images (Digest-pinned)
- IMAGE_REF: `123456789012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc`
- Digest: `sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc`

## Upgrade / Operational Notes
- None

## Changes (categorized)
- Added:
  - None
- Changed:
  - None
- Fixed:
  - None

## Breaking Changes
- None

## Known Issues
- None

## Proof References
- docs/proof/v1.md

## Why this release exists
- Major release.

## Compatibility Matrix
- None

## Deprecations Timeline
- None

## Integrity
- Main commit SHA: `3333333333333333333333333333333333333333`
- IMAGE_REF digest: `sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc`
- CI workflow URL: `https://github.com/penquinspecz/SignalCraft/actions/runs/999`
- CI run ID: `999`
- CI workflow: `release-ecr`
MD

run_expect_pass "$TMP_DIR/product-minor.md" --release-kind product --semver-level minor --tag v0.2.1 --require-ci-evidence
run_expect_fail "$TMP_DIR/product-missing-digest.md" --release-kind product --tag v0.2.1
run_expect_pass "$TMP_DIR/milestone-pass.md" --release-kind milestone --tag m19-20260222T201429Z
run_expect_fail "$TMP_DIR/product-major-missing-migration.md" --release-kind product --semver-level major --tag v1.0.0

echo "PASS: release-body validator smoke cases"
