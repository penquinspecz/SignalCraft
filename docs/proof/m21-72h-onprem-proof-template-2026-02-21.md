# M21 On-Prem 72h Stability Proof Template — 2026-02-21

Use this template during the real 72h run. Keep all values concrete.

## Run Inputs
- started_at_utc:
- operator:
- cluster_context:
- namespace:
- candidate_id:
- provider:
- profile:
- config_path: `config/defaults.json`
- providers_config_path: `config/providers.json`
- scoring_config_path: `config/scoring.v1.json`
- expected_duration_hours: 72
- expected_interval_minutes: 60

## Environment
```bash
export JOBINTEL_STATE_DIR=state
export JOBINTEL_DATA_DIR=data
export JOBINTEL_CANDIDATE_ID=<candidate_id>

kubectl config current-context
kubectl -n jobintel get cronjob,pods,jobs
```

## Command (Single Harness Entrypoint)
```bash
make m21-stability-harness \
  M21_DURATION_HOURS=72 \
  M21_INTERVAL_MINUTES=60 \
  M21_CANDIDATE_ID=<candidate_id> \
  M21_PROVIDER=<provider> \
  M21_PROFILE=<profile> \
  M21_KUBE_CONTEXT=<context>
```

Equivalent direct command:
```bash
PYTHONPATH=src .venv/bin/python scripts/m21_onprem_stability_harness.py \
  --duration-hours 72 \
  --interval-minutes 60 \
  --candidate-id <candidate_id> \
  --provider <provider> \
  --profile <profile> \
  --config config/defaults.json \
  --providers-config config/providers.json \
  --namespace jobintel \
  --kube-context <context> \
  --allow-run-id-drift
```

## Expected Receipt Paths
- `state/proofs/m21/<run_id>/start_receipt.json`
- `state/proofs/m21/<run_id>/checkpoints.jsonl`
- `state/proofs/m21/<run_id>/checkpoints/checkpoint-*/checkpoint.json`
- `state/proofs/m21/<run_id>/final_receipt.json`
- `state/proofs/m21/<run_id>/summary.json`
- `state/proofs/m21/<run_id>/final/replay.log`
- `state/proofs/m21/<run_id>/final/snapshot_immutability.log`
- `state/proofs/m21/<run_id>/final/determinism_compare.log`

## 72h Checkpoint Checklist
- [ ] T+00h: checkpoint recorded, pipeline pass/fail captured
- [ ] T+12h: checkpoint recorded, k8s pod/job snapshot captured
- [ ] T+24h: checkpoint recorded, success/failure counts reviewed
- [ ] T+36h: checkpoint recorded, artifact hash summary present
- [ ] T+48h: checkpoint recorded, no missing critical artifacts
- [ ] T+60h: checkpoint recorded, k8s resource snapshots continue
- [ ] T+72h: final checkpoint recorded
- [ ] replay strict check passed
- [ ] snapshot immutability check passed
- [ ] determinism compare vs baseline passed

## Final Summary (Fill After Run)
- run_id:
- intervals_completed:
- success_count:
- failure_count:
- final_status:
- fail_reasons:
- replay_returncode:
- snapshot_immutability_returncode:
- determinism_compare_returncode:
- notes:
