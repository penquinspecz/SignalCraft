# Ops Runbook (ECS + S3)

## Happy path
```bash
python scripts/preflight_env.py --mode verify --deployment-env prod
./scripts/deploy_ecs_rev.sh
TASKDEF_REV=<newrev> bash ./scripts/run_ecs_once.sh
BUCKET=jobintel-prod1 PREFIX=jobintel bash ./scripts/verify_ops.sh
BUCKET=jobintel-prod1 PREFIX=jobintel bash ./scripts/show_run_provenance.sh
aws s3 ls s3://jobintel-prod1/jobintel/latest/openai/cs/
./scripts/print_taskdef_env.sh TASKDEF_REV=<newrev>
```

## Redaction contract (prod)
```bash
export REDACTION_ENFORCE=1
python scripts/preflight_env.py --mode verify --deployment-env prod
```
- Production preflight is non-zero unless `REDACTION_ENFORCE=1`.
- Keep `REDACTION_ENFORCE=1` in production overlays/task definitions.

## Verify provenance
```bash
# Show build provenance from last_success (or provider/profile) pointer
BUCKET=jobintel-prod1 PREFIX=jobintel PROVIDER=openai PROFILE=cs bash ./scripts/show_run_provenance.sh
```
Note: ECS task ARN is resolved via ECS task metadata when available.

## Dashboard modes
- Minimal/offline mode (CI-safe): `make dashboard-sanity`
- Full dashboard mode (local dev): install extras then run `make dashboard`
- See: `docs/DASHBOARD.md`

## M21 on-prem 72h stability harness
Single-command entrypoint (receipt-driven, non-interactive):
```bash
make m21-stability-harness \
  M21_DURATION_HOURS=72 \
  M21_INTERVAL_MINUTES=60 \
  M21_CANDIDATE_ID=local \
  M21_PROVIDER=openai \
  M21_PROFILE=cs \
  M21_KUBE_CONTEXT=<context>
```

Kubernetes-native monitoring commands during run:
```bash
kubectl --context <context> -n jobintel get cronjob,pods,jobs
kubectl --context <context> -n jobintel top pods
kubectl --context <context> top nodes
kubectl --context <context> -n jobintel get events --sort-by=.metadata.creationTimestamp | tail -n 80
```

Harness receipts are written under `state/proofs/m21/<run_id>/`:
- `start_receipt.json`
- `checkpoints.jsonl`
- `checkpoints/checkpoint-*/checkpoint.json`
- `final_receipt.json`
- `summary.json`

Use template: `docs/proof/m21-72h-onprem-proof-template-2026-02-21.md`.

## Publish to S3
```bash
PUBLISH_S3=1 JOBINTEL_S3_BUCKET=jobintel-prod1 JOBINTEL_S3_PREFIX=jobintel \
  python scripts/run_daily.py --profiles cs --providers openai --no_post

aws s3 ls s3://jobintel-prod1/jobintel/runs/<run_id>/<provider>/<profile>/
aws s3 ls s3://jobintel-prod1/jobintel/latest/openai/cs/
```

## M19 Phase A: harden S3 retention controls
```bash
# Dry-run
make aws-s3-hardening

# Apply versioning + lifecycle changes (set backup bucket if available)
JOBINTEL_S3_BACKUP_BUCKET=<backup-bucket> APPLY=1 make aws-s3-hardening

# Validate controls
aws s3api get-bucket-versioning --bucket "$JOBINTEL_S3_BUCKET"
aws s3api get-bucket-lifecycle-configuration --bucket "$JOBINTEL_S3_BUCKET"
```

## Failure modes
```bash
# Pointers missing or access denied
BUCKET=jobintel-prod1 PREFIX=jobintel bash ./scripts/verify_ops.sh

# Show build provenance from last_success pointer
BUCKET=jobintel-prod1 PREFIX=jobintel bash ./scripts/show_run_provenance.sh

# Inspect task env + image
TASKDEF_REV=<newrev> ./scripts/print_taskdef_env.sh

# Inspect task runtime status
CLUSTER_ARN=<cluster> TASK_ARN=<task> REGION=us-east-1 ./scripts/ecs_verify_task.sh

# Publish disabled or missing bucket
PUBLISH_S3=1 python scripts/run_daily.py --profiles cs --providers openai --no_post
```

## Failure playbook (local / operator)

When a run fails, inspect artifacts in this order:

### 1. Force-fail demo (dev/test)

```bash
./scripts/dev/force_fail_demo.sh scrape
# or: ./scripts/dev/force_fail_demo.sh classify
```

Prints artifact paths and exits non-zero (expected). See [docs/proof/m12-forced-failure-receipts-2026-02-15.md](proof/m12-forced-failure-receipts-2026-02-15.md).

### 2. Inspect run artifacts via CLI

```bash
python -m jobintel.cli runs list --candidate-id local --limit 5
python -m jobintel.cli runs show <run_id> --candidate-id local
python -m jobintel.cli runs artifacts <run_id> --candidate-id local
```

### 3. Check first: failed_stage and failure_code

- **run_health.v1.json**: `failed_stage`, `failure_codes`, `status`
- **run_summary.v1.json**: `status`, `run_health.path`

Key failure codes:

| Code | Meaning |
|------|---------|
| `FORCED_FAILURE` | Dev harness (JOBINTEL_FORCE_FAIL_STAGE) |
| `SNAPSHOT_FETCH_FAILED` | Snapshot missing or parse failed |
| `policy_snapshot` | Provider disabled by config |
| `unavailable` / `network` | Provider fetch failed (live mode) |

### 4. provider_availability: policy vs network vs config

- **Terminal run invariant**: `artifacts/provider_availability_v1.json` is emitted once per finalized run (success, failure, or startup exit).
- **Early failure** (startup/scrape/classify): entries are fail-closed (`availability: "unavailable"`, reason code such as `early_failure_unknown`).
- **Zero-provider config**: disabled providers are still represented with `reason_code: "not_enabled"` so the state is explicit.
- **Differentiate**:
  - **Policy block**: `policy_snapshot` or `snapshot_disabled` → config/ops decision
  - **Network issue**: `unavailable`, `timeout`, fetch errors → infra/connectivity
  - **Config disable**: provider `enabled: false` in config

Proof: [docs/proof/m12-failure-playbook-receipts-2026-02-14.md](proof/m12-failure-playbook-receipts-2026-02-14.md)
