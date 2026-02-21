# M21 Harness Implementation Receipt — 2026-02-21

## Goal
Introduce a deterministic, receipt-driven starter harness for Milestone 21 (on-prem 72h stability proof) with a single non-interactive command suitable for local + Kubernetes CronJob execution.

## Deliverables
- Script: `scripts/m21_onprem_stability_harness.py`
- Make target: `make m21-stability-harness`
- Runbook updates: `docs/OPS_RUNBOOK.md`
- Proof template: `docs/proof/m21-72h-onprem-proof-template-2026-02-21.md`
- Tests: `tests/test_m21_onprem_stability_harness.py`

## Harness Contract
- Start receipt records timestamp, candidate/provider/profile, and config hashes.
- Each interval executes deterministic pipeline entrypoint (`scripts/run_daily.py` in snapshot-only mode), captures pass/fail, writes per-interval logs, and records artifact hash summary.
- Optional k8s snapshots (`kubectl`) are captured without requiring interactivity.
- Finalization runs:
  - `scripts/replay_run.py --strict --json`
  - `scripts/verify_snapshots_immutable.py`
  - `scripts/compare_run_artifacts.py` baseline vs latest success
- Final receipt is fail-closed when mandatory checks do not execute or fail.

## Example Command
```bash
make m21-stability-harness \
  M21_DURATION_HOURS=72 \
  M21_INTERVAL_MINUTES=60 \
  M21_CANDIDATE_ID=local \
  M21_PROVIDER=openai \
  M21_PROFILE=cs \
  M21_KUBE_CONTEXT=rancher-desktop
```

## Validation Commands
```bash
make format
make lint
make ci-fast
make gate
```

## Determinism/Replay Notes
- No scoring logic changes.
- No new runtime product surfaces.
- Harness is an ops receipt orchestrator only.
- Replay + snapshot immutability checks are mandatory in final receipt.
