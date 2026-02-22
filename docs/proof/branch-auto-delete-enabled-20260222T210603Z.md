# Branch Auto-Delete Enabled Receipt (2026-02-22)

## Setting

**delete_branch_on_merge:** enabled for penquinspecz/SignalCraft

## Command

```bash
gh repo edit penquinspecz/SignalCraft --delete-branch-on-merge
```

## Verification

```bash
gh api repos/penquinspecz/SignalCraft --jq '.delete_branch_on_merge'
# Expected: true
```

## Timestamp

2026-02-22T210603Z
