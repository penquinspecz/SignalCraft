# M23 Entropy Reduction PR2 - 2026-02-18

## Scope
Introduce a single canonical UTC ISO helper and replace a constrained set of duplicate wrappers (9 call sites) without changing runtime behavior.

## Canonical Helper Contract
File: `src/ji_engine/utils/time.py`

- `utc_now_iso(*, seconds_precision: bool = True) -> str`
- Returns ISO8601 UTC with trailing `Z`
- Default precision: seconds (microseconds zeroed)
- Optional microsecond precision when `seconds_precision=False`
- `utc_now_z` retained as a backward-compatible alias to avoid drift

## Duplicate Inventory (before)
Command:
```bash
rg -n "def (_utcnow_iso|_utc_now_iso|utc_now_iso|now_iso)\(" src scripts
```
Count: `15`

Paths:
- `src/jobintel/ai_insights.py`
- `src/jobintel/aws_runs.py`
- `src/jobintel/discord_notify.py`
- `scripts/ops/prove_m3_backoff_cb.py`
- `src/jobintel/snapshots/fetch.py`
- `scripts/smoke_metadata.py`
- `scripts/ops/eks_infra_plan_bundle.py`
- `src/jobintel/ai_job_briefs.py`
- `scripts/ops/capture_m3_infra_receipts.py`
- `scripts/update_snapshots.py`
- `scripts/prove_cloud_run.py`
- `src/ji_engine/ai/insights_input.py`
- `src/ji_engine/proof/liveproof.py`
- `src/ji_engine/pipeline/runner.py`
- `src/ji_engine/proof/bundle.py`

## Constrained Replacements (9 call sites)
1. `src/jobintel/ai_insights.py`
2. `src/jobintel/discord_notify.py`
3. `src/jobintel/ai_job_briefs.py`
4. `src/jobintel/snapshots/fetch.py`
5. `src/ji_engine/ai/insights_input.py`
6. `src/ji_engine/proof/liveproof.py`
7. `src/ji_engine/proof/bundle.py`
8. `scripts/smoke_metadata.py`
9. `scripts/update_snapshots.py`

## Duplicate Inventory (after)
Command:
```bash
rg -n "def (_utcnow_iso|_utc_now_iso|utc_now_iso|now_iso)\(" src scripts
```
Count: `7`

Remaining paths:
- `src/jobintel/aws_runs.py`
- `scripts/ops/prove_m3_backoff_cb.py`
- `scripts/prove_cloud_run.py`
- `scripts/ops/eks_infra_plan_bundle.py`
- `scripts/ops/capture_m3_infra_receipts.py`
- `src/ji_engine/utils/time.py` (canonical helper)
- `src/ji_engine/pipeline/runner.py`

Net reduction in local helper definitions: `15 -> 7` (`-8`).

## Tests Added/Updated
- `tests/test_time_utils.py`
  - `test_utc_now_iso_seconds_precision_default`
  - `test_utc_now_iso_microseconds_when_disabled`
  - `test_utc_now_z_aliases_canonical_iso`

## Validation Commands
```bash
make format
make lint
make ci-fast
make gate
```

## Validation Results
- `make format`: pass (`9 files reformatted`)
- `make lint`: pass
- `make ci-fast`: pass (`681 passed, 16 skipped`)
- `make gate`: pass (`681 passed, 16 skipped`)
- Snapshot immutability: pass
- Replay smoke: pass (`checked=6 matched=6 mismatched=0 missing=0`)

## Determinism / Replay Notes
- Timestamp format contract preserved (`UTC`, trailing `Z`, seconds precision default).
- No change to replay logic, artifact schemas, or pipeline stage ordering.
