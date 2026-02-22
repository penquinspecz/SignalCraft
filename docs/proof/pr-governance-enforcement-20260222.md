# PR Governance Enforcement Receipt (2026-02-22)

## Files Changed

- `.github/workflows/pr-governance.yml` — new: validates title, labels, milestone
- `.github/workflows/labeler.yml` — new: auto-labels area:* from paths
- `.github/labeler.yml` — new: path → area mappings
- `docs/LABELS.md` — new: taxonomy, enforcement rules, auto-labeling note
- `docs/RELEASE_PROCESS.md` — updated: PR Governance section with enforcement

## Rules Enforced (pr-governance.yml)

1. **Title:** Must NOT match `[from-(composer|codex|human)]` (case-insensitive)
2. **Provenance:** Exactly one of `from-composer`, `from-codex`, `from-human`
3. **Type:** Exactly one `type:*` label
4. **Area:** Exactly one `area:*` label
5. **Milestone:** Must be set (any milestone)

## Trigger Choice

- **pr-governance:** `pull_request` — we only read PR metadata via API, never checkout or run PR code. Safe for forks.
- **labeler:** `pull_request_target` — labeler needs `pull-requests: write` to add labels. Safe: no checkout of PR code.

## Labels Created

- `from-human` (provenance)

## Gates Run

| Gate | Result |
|------|--------|
| `./scripts/audit_determinism.sh` | PASS |
| `python3 scripts/ops/check_dr_docs.py` | PASS |
| `python3 scripts/ops/check_dr_guardrails.py` | PASS |
