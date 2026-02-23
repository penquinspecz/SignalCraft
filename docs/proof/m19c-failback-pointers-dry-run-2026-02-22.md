# Milestone 19C Proof - Deterministic Failback Pointers (2026-02-22)

## Scope
M19C DoD: deterministic failback command path exists (dry-run + apply).

- Added `scripts/ops/dr_failback_pointers.sh` for explicit pointer switchback.
- Dry-run (default): capture before state, verify, write plan receipt. No mutations.
- Apply: perform pointer updates, re-verify, write apply receipt.

## Receipt Contract
All receipts written to `--receipt-dir` (required). Deterministic ordering, explicit receipts, no hidden state.

| Receipt | Phase | Description |
|---------|-------|-------------|
| `drill.failback.inputs.json` | inputs | Bucket, prefix, primary-run-id, dr-run-id, provider, profile, region, dry_run |
| `drill.failback.verify_before.json` | verify_before | Global/provider pointer run_ids, expected_dr_run_id, pointers_match_dr |
| `drill.failback.plan.json` | plan | from_run_id, to_run_id, pointer_updates (key + payload), dry_run |
| `drill.failback.apply.json` | apply | applied, canonical_run_id, updated_keys (only when --apply) |
| `drill.failback.verify_after.json` | verify_after | Post-apply pointer verification (only when --apply) |
| `drill.failback.phase_timestamps.json` | complete | Phase timestamps (inputs, verify_before, compare, plan, apply, verify_after, complete) |

## Verification Steps
1. Account/region contract: `aws sts get-caller-identity` vs `--expected-account-id`
2. Before pointers: fetch global/provider `last_success.json`, assert match `--dr-run-id`
3. Verify published S3: `scripts/verify_published_s3.py` with `--run-dir` (DR run)
4. Compare artifacts: `scripts/compare_run_artifacts.py` primary vs DR (if both run_summary exist)
5. Plan: build pointer payload from primary run_summary
6. Apply (if `--apply`): write pointers to S3, re-fetch, verify match primary

## Gates
- `./scripts/audit_determinism.sh` — PASS
- `python3 scripts/ops/check_dr_docs.py` — PASS
- `python3 scripts/ops/check_dr_guardrails.py` — PASS

## Evidence
- `scripts/ops/dr_failback_pointers.sh`
- `docs/dr_promote_failback.md` (Deterministic Failback Pointers section)
- `scripts/ops/check_dr_docs.py` (needle: scripts/ops/dr_failback_pointers.sh)
