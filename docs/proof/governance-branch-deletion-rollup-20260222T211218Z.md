# Governance Branch Deletion Rollup (2026-02-22)

## Repo Setting

**delete_branch_on_merge:** enabled via `gh repo edit penquinspecz/SignalCraft --delete-branch-on-merge`

## Merged PRs

| PR | Title | Merged | Branch | Branch Deleted |
|----|-------|--------|--------|----------------|
| 224 | chore(governance): enforce branch deletion on merge | 2026-02-22T21:08:30Z | chore/governance-branch-auto-delete-20260222T210603Z | Yes |
| 217 | chore(docs): establish versioning + release template | 2026-02-22T21:09:25Z | chore/docs-versioning-release-template-20260222T202545Z | Yes |
| 218 | chore(release): add release notes renderer | 2026-02-22T21:10:48Z | chore/release-render-release-notes-20260222T202643Z | Yes |
| 219 | docs: define product release policy (v0.2.0 readiness) | — | chore/docs-v020-release-policy-20260222T203548Z | Pending merge |
| 220 | chore(governance): PR template + milestone policy (B) | — | chore/pr-governance-milestoneB-20260222T204028Z | Pending merge |

## Branch Deletion Verification

- **224:** `git ls-remote origin refs/heads/chore/governance-branch-auto-delete-20260222T210603Z` → empty (deleted)
- **217:** `git ls-remote origin refs/heads/chore/docs-versioning-release-template-20260222T202545Z` → empty (deleted)
- **218:** `git ls-remote origin refs/heads/chore/release-render-release-notes-20260222T202643Z` → empty (deleted)

## Final Sync

- `git pull origin main` — done
- `./scripts/audit_determinism.sh` — PASS

## Pending

- **219:** Merge when gate completes. Branch updated with main; conflict resolved.
- **220:** Largely superseded by 221, 223, 224. Consider closing or resolving conflicts.
