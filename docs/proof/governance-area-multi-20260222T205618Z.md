# Governance Area Multi-Label Relaxation Receipt (2026-02-22)

## Summary

Relaxed PR governance to allow multiple area labels (>=1) instead of exactly one.

## Rule Change

- **Before:** Exactly one `area:*` label required
- **After:** At least one `area:*` label required (multiple allowed)

## Files Changed

- `.github/workflows/pr-governance.yml` — area check: `!== 1` → `< 1`
- `docs/LABELS.md` — "Exactly one" → "At least one (multiple allowed)"
- `docs/RELEASE_PROCESS.md` — same

## Gates Run

| Gate | Result |
|------|--------|
| `./scripts/audit_determinism.sh` | PASS |
| `python3 scripts/ops/check_dr_docs.py` | PASS |
| `python3 scripts/ops/check_dr_guardrails.py` | PASS |

## PR / Commit

- Branch: `chore/governance-relax-area-multi-20260222T205618Z`
- Commit: (see PR)
