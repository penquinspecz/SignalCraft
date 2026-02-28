# Release Notes Style Guide

Defines how milestone (m*) and product (v*) releases should be written.

## Milestone Release (m*)

- **Structured, proof-first, self-contained.** No external-doc dependency to understand status.
- **Required headings:** Milestone Context, What was exercised, Execution Evidence, Images (Digest-pinned), Guardrails/Determinism checks, Outcome + Next steps, Proof References.
- **Always include:** digest-pinned IMAGE_REF (unless explicit dev override), execution evidence, and receipt paths.
- Use `scripts/release/render_release_notes.py --release-kind milestone` (default).

## Product Release (v*)

- **Readable first, auditable second.**
- **Required headings (minor/patch):** Highlights, What's Proven (Operator Reality Check), Images (Digest-pinned), Upgrade / Operational Notes, Changes (categorized), Breaking Changes, Known Issues, Proof References, Integrity.
- **Major adds required headings:** Why this release exists, Migration / Upgrade Guide, Compatibility Matrix, Deprecations Timeline.
- **Digest-pinned IMAGE_REF required for non-dev releases.**
- Use `scripts/release/render_release_notes.py --release-kind product`.

## Common

- Both kinds: deterministic output given inputs.
- Validator (`scripts/release/validate_release_body.py`) blocks non-compliant bodies before publish.
- Receipt paths anchor proof.

See also: `docs/RELEASE_TEMPLATE_PRODUCT.md`, `docs/RELEASE_TEMPLATE_MILESTONE.md`, `docs/VERSIONING.md`.
