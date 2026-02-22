# Release Process (Deterministic, Least-Annoying)

This is the canonical release discipline for SignalCraft.

See also: `docs/VERSIONING.md` (dual-track versioning), `docs/RELEASE_TEMPLATE.md` (release body template).

---

## PR Governance

### Titles and Provenance

- **PR titles never contain `[from-composer]`.** Provenance is tracked via labels only.
- **Required labels for merge:** `type:*`, `area:*`, and `from-composer` when the PR was authored via Composer.

### Milestone B Rule

- **Milestones are REQUIRED** for roadmap/MXX work.
- **Milestones are OPTIONAL** for ad hoc work **only if** the PR is assigned to one of these bucket milestones:
  - **Infra & Tooling**
  - **Docs & Governance**
  - **Backlog Cleanup**
- For ad hoc work: use a bucket milestone, or justify in the PR description why no milestone applies.
- **Recommendation:** Add a Milestone only when work is roadmap/MXX; otherwise use a bucket milestone.

### Release Notes vs PR Titles

- Release notes may include `[from-composer]` as a header line or in PR lists.
- PR titles must not contain `[from-composer]`.
- PRs may be listed in releases regardless of provenance label.

---

## Release-Intent Policy

A PR is **release-intent** when any of the following is true:
- PR has label `release`
- `pyproject.toml` version changes
- Contract-surface files change:
  - `schemas/*.schema.v*.json`
  - `src/ji_engine/pipeline/artifact_paths.py`
  - `src/ji_engine/artifacts/catalog.py`

For release-intent PRs, `CHANGELOG.md` must be updated in the same PR.

If none of the above triggers, changelog update is not required.

## What Usually Does NOT Require CHANGELOG.md
- Test-only refactors
- Internal tooling/docs updates
- CI-only adjustments without user-visible contract changes
- Dashboard/offline sanity checks that do not change artifact contracts

## What Usually DOES Require CHANGELOG.md
- Breaking behavior changes
- New artifact contract or schema changes
- Changes to artifact catalog/pathing contract
- New provider additions or provider contract changes
- Version bump/tag prep

## Required Release Steps (when doing a release)
1. Sync `main` and ensure clean worktree.
2. Run deterministic hygiene:
   - `make lint`
   - `make ci-fast`
   - `make gate`
3. Update `CHANGELOG.md` and ensure release-intent policy passes.
4. Bump version source of truth (`pyproject.toml`) if applicable.
5. Merge release prep PR to `main`.
6. Create annotated tag and push.
7. Publish release notes from the tag.

## Reproducible Build Verification (Clean Room)

Run this from a fresh clone directory with no pre-existing `.venv`:

```bash
git clone <repo-url> signalcraft-cleanroom
cd signalcraft-cleanroom
git checkout main
make tooling-sync
make lint
make ci-fast
make gate
```

Notes:
- `make tooling-sync` creates `.venv` deterministically and pins tooling versions.
- Dashboard extras are optional and not required for `make ci-fast` or `make gate`.
- Use `make dashboard-sanity` for dashboard contract verification without installing extras.

## Copy/Paste Commands

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git status -sb

make lint
make ci-fast
make gate
```

```bash
# Example for v0.1.0
git tag -a v0.1.0 -m "SignalCraft v0.1.0"
git push origin v0.1.0
gh release create v0.1.0 --generate-notes --title "v0.1.0"
```

## Determinism Notes
- CI changelog policy runs in PR fast job only.
- Policy uses local git diff + event payload only; no GitHub API/network calls.
- Missing event payload is handled safely (non-strict mode); strict fixture mode is available via `make release-policy`.
