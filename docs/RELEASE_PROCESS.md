# Release Process (Deterministic, Least-Annoying)

This is the canonical release discipline for SignalCraft.

See also: `docs/VERSIONING.md` (dual-track versioning), `docs/RELEASE_TEMPLATE.md` (release body template), `docs/BRANCHING.md` (branch lifecycle).

---

## When to Cut a Product Release (SemVer)

Cut a product release when:

- A user-facing capability is complete and stable at a milestone boundary.
- Deterministic gates and policy checks pass.
- No release is valid unless the proof requirements in `docs/VERSIONING.md` are met.

---

## How Product Releases Differ from Milestone Releases

| Aspect | Product (SemVer) | Milestone (timestamped) |
|--------|------------------|-------------------------|
| Tags | `v0.2.0`, `v0.2.1` | `m19-20260222T201429Z` |
| Purpose | User-facing capability; contract stability | Operational proof; DR drills; infra audit |
| Frequency | At milestone boundaries | As needed to anchor proof |
| Body | CHANGELOG-driven; optional IMAGE_REF | IMAGE_REF, digest, archs, PRs, receipts required |

---

## v0.2.0 Definition of Done

- [ ] canonical deterministic entrypoint stable
- [ ] snapshot immutability + replay smoke enforced
- [ ] multi-arch digest-pinned image build + metadata exists
- [ ] DR operator workflow cost discipline + explicit full-drill allow guardrail exists
- [ ] DR validate proves job runs in restored cluster without manual auth/patching
- [ ] runbooks and doc lint match reality (guardrails + docs checks pass)

---

## Branch Lifecycle

- Short-lived branches only; auto-delete on merge (repo setting).
- Exceptions: none for now; revisit for marketing/product release workflows.

---

## PR Governance

**Enforcement:** `.github/workflows/pr-governance.yml` blocks merge when rules are violated.

### Titles and Provenance

- **PR titles never contain `[from-composer]`, `[from-codex]`, or `[from-human]`.** Provenance is label-only.
- **Required labels for merge (enforced):**
  - Exactly one provenance: `from-composer`, `from-codex`, or `from-human`
  - Exactly one `type:*` (feat, fix, chore, docs, refactor, test)
  - At least one `area:*` (engine, providers, dr, release, infra, docs; multiple allowed)
  - Milestone must be set (any milestone)

### Milestone B Rule

- **Milestones are REQUIRED** for all PRs (CI enforces).
- For roadmap/MXX work: use the corresponding milestone.
- For ad hoc work: use a bucket milestone — **Infra & Tooling**, **Docs & Governance**, or **Backlog Cleanup**.

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
