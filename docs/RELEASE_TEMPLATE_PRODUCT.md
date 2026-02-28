# SignalCraft Product Release Template

Use this for `vX.Y.Z` releases.

Release class:
- MAJOR: include the required MAJOR-only sections below
- MINOR/PATCH: MAJOR-only sections are optional

## Highlights
- <concise capability summary>
- <concise capability summary>

## What’s Proven (Operator Reality Check)
- <explicit statement of what was exercised and verified>
- <explicit statement of what was exercised and verified>

## Images (Digest-pinned)
- IMAGE_REF: `<account>.dkr.ecr.<region>.amazonaws.com/<repo>@sha256:<64-hex>`
- Digest: `sha256:<64-hex>`
- Architectures: `amd64, arm64`

## Upgrade / Operational Notes
- <operator-facing upgrade note or "None">

## Changes (categorized)
- Added:
  - <item or "None">
- Changed:
  - <item or "None">
- Fixed:
  - <item or "None">

## Breaking Changes
- None

## Known Issues
- None

## Proof References (repo paths)
- `docs/proof/<proof-doc-1>.md`
- `docs/proof/<proof-doc-2>.md`

## Integrity
- Main commit SHA: `<40-char SHA>`
- IMAGE_REF digest: `sha256:<64-hex>`
- CI workflow URL: `https://github.com/<org>/<repo>/actions/runs/<id>` or `Not recorded at tag time`
- CI run ID: `<run-id>` or `Not recorded at tag time`
- CI workflow: `<name>` or `Not recorded at tag time`

## MAJOR: Why this release exists
- <required for MAJOR releases>

## MAJOR: Migration / Upgrade Guide
- <required for MAJOR releases>

## MAJOR: Compatibility Matrix
- Runtime/Platform: <version support statement>
- API/Schema: <version support statement>

## MAJOR: Deprecations Timeline
- <required for MAJOR releases>
