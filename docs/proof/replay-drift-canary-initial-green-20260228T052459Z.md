# Replay Drift Canary: Initial Green Proof

Date (UTC): 2026-02-28T05:24:59Z

## Goal
Prove the scheduled replay drift canary logic is deterministic using pinned fixtures and emits a machine-readable receipt.

## Canonical fixture inputs
- `data/openai_snapshots/index.html`
- `data/candidate_profile.json`

## Command run
```bash
PYTHONPATH=src .venv/bin/python scripts/replay_drift_canary.py \
  --provider openai \
  --profile cs \
  --diff-out docs/proof/replay-drift-canary-receipt-20260228T052459Z.json
```

## Result
- Exit code: `0`
- Status: `pass`
- Receipt: `docs/proof/replay-drift-canary-receipt-20260228T052459Z.json`

## Receipt checks (all pass)
- `artifact_hashes`
- `identity_normalization`
- `provider_availability`
- `compare_run_artifacts`

## Determinism/safety notes
- Fixture-only execution (`CAREERS_MODE=SNAPSHOT`, `--offline`), no live network dependency.
- Runs execute in isolated temp workdirs; no production artifacts are mutated.
- Drift emits machine-readable JSON and fails the canary workflow when mismatches are detected.
