# Release Notes Render Example (m19)

Example output from `scripts/release/render_release_notes.py --release-kind milestone` for tag `m19-20260222T201429Z`.

## Command

```bash
python3 scripts/release/render_release_notes.py --release-kind milestone \
  --tag m19-20260222T201429Z \
  --main-sha 06746a1c334cf6a0411cce4359934fa16322bffb \
  --image-ref 123456789.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:abc123def456 \
  --arch amd64 --arch arm64 \
  --prs 213,214,215,216 \
  --receipts docs/proof/m19-dr-rehearsal-20260221.md \
  --why "DR cost discipline guardrails" --why "S3 versioning proof"
```

## Rendered Output

```markdown
## Why this release exists
- DR cost discipline guardrails
- S3 versioning proof

## main HEAD
- SHA: `06746a1c334cf6a0411cce4359934fa16322bffb`

## IMAGE_REF (digest pinned)
`123456789.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:abc123def456`

Architectures verified: `amd64, arm64`

## PRs included
- #213
- #214
- #215
- #216

## Proof / Receipts
- docs/proof/m19-dr-rehearsal-20260221.md
```

## Determinism

Same inputs produce same output. PRs and receipts are sorted for stable ordering.
