# M19 Phase B Proof Template: AWS DR Rehearsal (Bringup -> Restore -> Run -> Publish Verify -> Teardown)

Status: TEMPLATE (fill during live rehearsal)

## 0) Rehearsal Metadata
- Operator:
- Date (UTC):
- Git commit SHA:
- AWS account (from STS):
- AWS region:
- Namespace:
- Backup URI:
- S3 bucket:
- S3 prefix:
- Run ID (once known):
- DR validation job name (once known):

## 1) Authoritative Runbook + Scope
Authoritative execution runbook:
- `ops/dr/RUNBOOK_DISASTER_RECOVERY.md`

Supporting overview:
- `ops/dr/README.md`

Execution scope for this receipt:
- bringup
- restore contract validation
- run validation job
- publish verification
- teardown
- teardown safety check (no lingering DR compute)

## 2) Exact Commands Executed
Paste exactly what you ran (no edits after the fact).

```bash
# Required env (set values before running)
export AWS_REGION=<aws-region>
export NAMESPACE=jobintel
export BACKUP_URI=s3://<bucket>/<prefix>/backups/<backup_id>
export BUCKET=<bucket>
export PREFIX=<prefix>

# Optional: pin receipt dir
export RECEIPT_DIR=ops/proof/bundles/m19-<run_id>
mkdir -p "$RECEIPT_DIR"

# Preflight
aws sts get-caller-identity
terraform -chdir=ops/dr/terraform version
scripts/ops/dr_contract.py --backup-uri "$BACKUP_URI"

# Bringup (plan + apply)
APPLY=0 scripts/ops/dr_bringup.sh
APPLY=1 scripts/ops/dr_bringup.sh

# Restore contract check
scripts/ops/dr_restore.sh --backup-uri "$BACKUP_URI"

# Run validation job
RUN_JOB=1 NAMESPACE="$NAMESPACE" scripts/ops/dr_validate.sh

# Identify created DR validation job deterministically (no jq required)
DR_JOB_NAME="$(kubectl -n "$NAMESPACE" get jobs -o name \
  | sed 's#job.batch/##' \
  | rg '^jobintel-dr-validate-' \
  | tail -n 1)"
echo "DR_JOB_NAME=$DR_JOB_NAME"

# Extract run_id + validate provenance/publish markers in logs
NS="$NAMESPACE" scripts/verify_last_job_run.sh "$DR_JOB_NAME"

# Parse run_id from previous output or directly from logs
RUN_ID="$(kubectl -n "$NAMESPACE" logs "job/$DR_JOB_NAME" | sed -n 's/.*JOBINTEL_RUN_ID=//p' | head -n 1)"
echo "RUN_ID=$RUN_ID"

# Publish verification (authoritative)
python scripts/verify_published_s3.py --bucket "$BUCKET" --run-id "$RUN_ID" --prefix "$PREFIX" --verify-latest

# Capture backup metadata for RPO input
aws s3 cp "$BACKUP_URI/metadata.json" - > "$RECEIPT_DIR/backup_metadata.json"

# Teardown
CONFIRM_DESTROY=1 scripts/ops/dr_teardown.sh

# No-lingering-resources safety checks
aws ec2 describe-instances --filters Name=tag:Project,Values=jobintel-dr Name=instance-state-name,Values=running
aws eks list-clusters
```

## 3) UTC Timing Capture (for RTO / RPO inputs)
Record these immediately during execution.

```text
T0_preflight_start_utc=
T1_bringup_apply_done_utc=
T2_restore_check_done_utc=
T3_validation_job_complete_utc=
T4_publish_verify_done_utc=
T5_teardown_done_utc=
```

RTO inputs:
- `recovery_start_utc` = `T0_preflight_start_utc`
- `service_validation_utc` = `T4_publish_verify_done_utc`
- `teardown_complete_utc` = `T5_teardown_done_utc`

Measured values:
- `RTO_to_publish_verify_seconds` = (`T4` - `T0`)
- `RTO_end_to_end_seconds` = (`T5` - `T0`)

RPO inputs:
- Backup point timestamp from `metadata.json` under `BACKUP_URI`:
  - `backup_point_utc`
- Recovered run start timestamp:
  - `recovered_run_start_utc` (from run logs/metadata)

Measured value:
- `RPO_seconds` = (`recovered_run_start_utc` - `backup_point_utc`)

## 4) Raw Outputs (Paste Unmodified)
### 4.1 STS identity
```text
<paste output>
```

### 4.2 `dr_contract` output
```text
<paste output>
```

### 4.3 Bringup plan/apply output
```text
<paste output>
```

### 4.4 Restore check output
```text
<paste output>
```

### 4.5 Validation job output
```text
<paste output>
```

### 4.6 `verify_last_job_run.sh` output
```text
<paste output>
```

### 4.7 `verify_published_s3.py` output
```text
<paste output>
```

### 4.8 Teardown output
```text
<paste output>
```

### 4.9 Backup metadata (`metadata.json`)
```text
<paste output>
```

### 4.10 No-lingering-resource checks
```text
<paste output>
```

## 5) PASS/FAIL Matrix
- Preflight (STS + terraform + backup contract):
- Bringup apply:
- Restore contract check:
- Validation run completed:
- Publish verification (`verify_published_s3`):
- Teardown completed:
- Lingering resources absent:

Overall Phase B result:
- PASS / FAIL

## 6) Artifacts Produced
- Proof bundle dir used:
- Logs captured:
- Run ID:
- S3 keys/pointers verified:

## 7) Notes / Deviations
- Any deviation from `ops/dr/RUNBOOK_DISASTER_RECOVERY.md`:
- Any retries and reason:
- Open follow-ups for Phase C:
