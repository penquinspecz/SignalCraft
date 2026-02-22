# Release Notes Style Guide

Defines how milestone (m*) and product (v*) releases should be written.

## Milestone Release (m*)

- **Structured, proof-first.** No long narrative.
- **Short rationale:** "Why this release exists" (1–3 bullets).
- **Always include:** main SHA, IMAGE_REF (digest-pinned), architectures, PR list, receipt paths.
- Use `scripts/release/render_release_notes.py --release-kind milestone` (default).

## Product Release (v*)

- **Narrative + highlights + migration notes.**
- **Sections:** Highlights, Breaking changes, Upgrade notes, Known issues.
- **CHANGELOG-driven.** Optional IMAGE_REF.
- Use `scripts/release/render_release_notes.py --release-kind product`.

## Common

- Both kinds: deterministic output given inputs.
- Receipt paths anchor proof.

See also: `docs/RELEASE_TEMPLATE.md`, `docs/VERSIONING.md`.
