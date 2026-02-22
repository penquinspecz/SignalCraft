# Cleanup Rollup Receipt (2026-02-22)

## PRs Closed

| PR | Action | Comment |
|----|--------|---------|
| 220 | Closed | Superseded by #221, #223, #224 |

## PRs Merged

| PR | Branch | Branch Deleted |
|----|--------|----------------|
| 225 | chore/add-rollup-receipt-20260222T211218Z | Yes (auto) |

## Branches Deleted

| Branch | Reason |
|--------|--------|
| chore/pr-governance-milestoneB-20260222T204028Z | PR 220 closed |
| chore/dr-land-local-script-fixes-20260222T201310Z | PR 216 merged |
| chore/governance-relax-area-multi-20260222T205618Z | PR 222 closed |
| chore/governance-relax-area-multi-v2 | PR 223 merged |
| chore/pr-governance-enforcement | PR 221 merged |

## Final State

- **Open PRs:** 0
- **Remote branches:** main only
- **delete_branch_on_merge:** true

## Commands Run

```bash
# Close PR 220
gh pr close 220 --comment "Superseded by #221, #223, #224"

# Delete 220 branch (closed PR)
git push origin --delete chore/pr-governance-milestoneB-20260222T204028Z

# Merge PR 225
gh pr merge 225 --squash --admin

# Delete stale branches
git push origin --delete chore/dr-land-local-script-fixes-20260222T201310Z
git push origin --delete chore/governance-relax-area-multi-20260222T205618Z
git push origin --delete chore/governance-relax-area-multi-v2
git push origin --delete chore/pr-governance-enforcement

# Verify
gh api repos/penquinspecz/SignalCraft --jq '.delete_branch_on_merge'
# Output: true

gh pr list --state open
# Output: (empty)

gh api repos/penquinspecz/SignalCraft/branches --jq '.[].name'
# Output: main
```

## Timestamp

2026-02-22T211723Z
