# Release Template (SignalCraft)

> Use this template for GitHub Releases. Replace placeholders.
> See `docs/RELEASE_NOTES_STYLE.md` for milestone vs product style. Use `scripts/release/render_release_notes.py` for deterministic output.

[from-composer]

## Context
This release advances <Milestone or Version>.

## main HEAD
- SHA: `<sha>`

## IMAGE_REF (digest pinned)
`<account>.dkr.ecr.<region>.amazonaws.com/<repo>@sha256:<digest>`

Architectures verified: `<amd64, arm64>`

## PRs included
- #<id> ...
- #<id> ...

## Operational Impact
- <bullet>
- <bullet>
- <bullet>

## Proof / Receipts
- Build/Push receipts: `<path>`
- Arch verify receipts: `<path>`
- DR proof receipts: `<path>` (if applicable)

## Notes
- <optional>
