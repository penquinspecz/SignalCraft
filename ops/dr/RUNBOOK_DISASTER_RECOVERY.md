# Runbook: Disaster Recovery (Canonical Entry Point)

This is the canonical operator document for DR execution.
If another DR doc conflicts with this runbook, follow this runbook.

## Operator Quickstart (Copy/Paste)

```bash
set -euo pipefail

export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
export AWS_PAGER=""
export EXPECTED_ACCOUNT_ID=048622080012

# Remote Terraform backend (required for DR mutation paths)
export TF_BACKEND_MODE=remote
export TF_BACKEND_BUCKET=<tf-backend-bucket>
export TF_BACKEND_KEY=signalcraft/dr/terraform.tfstate
export TF_BACKEND_DYNAMODB_TABLE=<tf-lock-table>

# DR network vars
export TF_VAR_vpc_id=vpc-4362fc3e
export TF_VAR_subnet_id=subnet-11001d5c

# DR data/release inputs
export BUCKET=<artifact-bucket>
export PREFIX=jobintel
export BACKUP_URI=s3://$BUCKET/$PREFIX/backups/<backup_id>
export IMAGE_REF=<account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest>

# 1) Publish control-plane continuity bundle from primary
scripts/control_plane/publish_bundle.sh \
  --bucket "$BUCKET" \
  --prefix "$PREFIX" \
  --image-ref-digest "$IMAGE_REF"

# 2) Full deterministic rehearsal (bringup -> restore -> validate -> optional promote -> teardown)
scripts/ops/dr_drill.sh \
  --backup-uri "$BACKUP_URI" \
  --image-ref "$IMAGE_REF" \
  --auto-promote false \
  --teardown true
```

## Preflight Checks

- Confirm AWS account is `048622080012` and region is `us-east-1`.
- Confirm `enable_triggers=false` unless explicitly testing automatic trigger paths.
- Confirm DR runner sizing defaults are in place:
  - `TF_VAR_instance_type` default is `t4g.medium` (ARM, reliable for restore+validate).
  - Override is allowed, but keep `t4g.*` family for ARM parity.
- Confirm digest-pinned `IMAGE_REF` is available in ECR and multi-arch metadata exists.
- Confirm backup contract objects exist at `BACKUP_URI`.
- Confirm `control-plane/current.json` exists (or bootstrap once from primary).

## Success Criteria

- DR bringup, restore, and validate complete with receipts.
- Manual promotion gate is explicit and auditable.
- Control-plane bundle URI/hash and validation outputs are receipted.
- Teardown leaves zero DR runners unless operator explicitly holds environment.

## If It Fails

- Stop at the failing phase; do not continue downstream phases.
- Capture failing command, stderr tail, and receipt location.
- Apply minimal fix, then rerun only the failed phase.
- If automation path fails, execute the equivalent manual runbook command and receipt it.

---

## A) Trigger Semantics (Manual vs Scheduled vs Alarm)

Manual trigger paths:
- `scripts/ops/dr_drill.sh` for deterministic rehearsals.
- Step Functions execution start for orchestrator-driven runs.

Scheduled/alarm-triggered orchestrator paths are safe-by-default:
- `enable_triggers` default is `false`.
- With `enable_triggers=false`, EventBridge schedule and alarm actions are created but disabled.

Enable/disable behavior is managed in orchestrator Terraform (`ops/dr/orchestrator`):

```bash
terraform -chdir=ops/dr/orchestrator apply \
  -var "region=us-east-1" \
  -var "expected_account_id=048622080012" \
  -var "enable_triggers=false" \
  -var "publish_bucket=<bucket>" \
  -var "backup_bucket=<bucket>" \
  -var "backup_uri=s3://<bucket>/<prefix>/backups/<backup_id>" \
  -var "receipt_bucket=<bucket>" \
  -var "notification_topic_arn=arn:aws:sns:us-east-1:048622080012:<topic>" \
  -var "dr_vpc_id=<vpc-id>" \
  -var "dr_subnet_id=<subnet-id>"
```

---

## B) Release Image Selection (Tag vs Digest, Multi-Arch)

DR should use digest-pinned image refs:
- Required format: `<repo>@sha256:<digest>`
- Example: `<account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest>`

Tag refs (`<repo>:<tag>`) are dev-only fallback and not preferred for DR.

Release pipeline guarantees:
- Multi-arch image under one commit tag (`linux/amd64` + `linux/arm64`)
- Release metadata includes digest and architectures

Typical release-safe flow:

```bash
export IMAGE_TAG="$(git rev-parse HEAD)"
scripts/release/build_and_push_ecr.sh
export RELEASE_METADATA="ops/proof/releases/release-${IMAGE_TAG}.json"
export IMAGE_REF="$(python3 - <<'PY' "$RELEASE_METADATA"
import json,sys
print(json.load(open(sys.argv[1], 'r', encoding='utf-8'))['image_ref_digest'])
PY
)"
```

---

## C) Control Plane Continuity (What State Carries Over)

Control Plane Bundle contents:
- `candidates/`
- `alerts/`
- `providers/`
- `scoring/`
- `manifest.json` (hashes + metadata)

Pointer semantics:
- Bundle objects: `s3://<bucket>/<prefix>/control-plane/bundles/<timestamp>-<shortsha>.tar.gz`
- Current pointer: `s3://<bucket>/<prefix>/control-plane/current.json`
- `current.json` fields: `bundle_uri`, `bundle_sha256`, `created_at`, `git_sha`, `image_ref_digest`

Publish (primary side):

```bash
scripts/control_plane/publish_bundle.sh \
  --bucket <bucket> \
  --prefix <prefix> \
  --image-ref-digest <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest>
```

Fetch and verify bundle (operator inspection):

```bash
scripts/control_plane/fetch_bundle.sh \
  --bucket <bucket> \
  --prefix <prefix> \
  --dest-dir /tmp/control-plane-fetch
```

Render deterministic k8s YAML (without apply):

```bash
scripts/control_plane/apply_bundle_k8s.sh \
  --bundle-dir /tmp/control-plane-fetch/bundle/control-plane \
  --namespace jobintel \
  --render-only \
  --output-yaml /tmp/control-plane.configmaps.yaml
```

Bootstrap rule:
- If `control-plane/current.json` is missing, run `publish_bundle.sh` once from primary before DR restore.

---

## D) Restore + Validate Flow

Backup URI contract (`scripts/ops/dr_contract.py`):
- `metadata.json`
- `state.tar.zst`
- `manifests.tar.zst`

Bring up + restore + validate (manual path):

```bash
APPLY=1 scripts/ops/dr_bringup.sh

scripts/ops/dr_restore.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --kubeconfig /tmp/.../k3s.public.yaml \
  --namespace jobintel

KUBECONFIG=/tmp/.../k3s.public.yaml \
RUN_JOB=1 \
NAMESPACE=jobintel \
IMAGE_REF=<account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
scripts/ops/dr_validate.sh
```

`dr_restore.sh` now enforces control-plane continuity before validate by:
- fetching `control-plane/current.json`
- verifying bundle hash
- ensuring the target namespace exists (no manual pre-create step required)
- ensuring ECR pull auth secret `ecr-pull` is created/refreshed and linked to ServiceAccount `jobintel`
- applying control-plane ConfigMaps into DR namespace
- applying baseline workloads from `ops/k8s/jobintel`
- gating on `cronjob.batch/jobintel-daily` existence before restore can pass

Validate reliability defaults:
- Validate job resources are pinned deterministically:
  - requests: `cpu=250m`, `memory=512Mi`
  - limits: `cpu=1`, `memory=2Gi`
- Validate retry policy is bounded:
  - retries only for `ErrImagePull`/pull-auth or `Insufficient memory`
  - max retries default: `2` (`DR_VALIDATE_MAX_RETRIES`)
  - short backoff default: `15s` base (`DR_VALIDATE_RETRY_BACKOFF_SECONDS`)

Safe override knobs:

```bash
# Infra sizing override (keep ARM family)
export TF_VAR_instance_type=t4g.large

# Validate resource overrides (only if required by workload profile)
export VALIDATE_REQUEST_CPU=300m
export VALIDATE_REQUEST_MEMORY=640Mi
export VALIDATE_LIMIT_CPU=1
export VALIDATE_LIMIT_MEMORY=2Gi

# Retry behavior override
export DR_VALIDATE_MAX_RETRIES=2
export DR_VALIDATE_RETRY_BACKOFF_SECONDS=15
```

ECR pull secret helper (manual/operator verification path):

```bash
scripts/ops/dr_ensure_ecr_pull_secret.sh \
  --namespace jobintel \
  --aws-region us-east-1 \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --secret-name ecr-pull \
  --service-account jobintel \
  --kubeconfig /tmp/.../k3s.public.yaml \
  --receipt-dir /tmp/.../ecr-pull-secret
```

Dry-run preflight (no cluster mutation):

```bash
scripts/ops/dr_ensure_ecr_pull_secret.sh \
  --namespace jobintel \
  --aws-region us-east-1 \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --kubeconfig /tmp/.../k3s.public.yaml \
  --dry-run
```

---

## E) Promotion / Go-Live Semantics

Current batch-mode promote means:
- DR validated and receipted
- Operator-approved decision
- DR publish pointers treated as canonical for batch consumers

Current promote does not do:
- DNS/endpoint cutover
- automatic traffic switching

Manual gate tooling (orchestrator):

```bash
scripts/ops/dr_status.sh \
  --state-machine-arn arn:aws:states:us-east-1:048622080012:stateMachine:signalcraft-dr-orchestrator-state-machine \
  --region us-east-1 \
  --expected-account-id 048622080012

scripts/ops/dr_approve.sh \
  --execution-arn arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:<execution-id> \
  --region us-east-1 \
  --expected-account-id 048622080012 \
  --approver <name> \
  --ticket <change-ticket>
```

Drill-only promotion bypass:
- `scripts/ops/dr_drill.sh --auto-promote true --allow-promote-bypass true`
- Intended only for controlled rehearsal, not production promotion.

---

## F) Failback Semantics (Safety + Divergence Checks)

Failback tool:
- `scripts/ops/dr_failback.sh`

Safety gates include:
- two explicit operator confirmations
- DR promoted precondition checks
- freeze DR scheduling + no in-flight jobs
- publish-pointer and artifact divergence verification
- optional teardown (default true)

Command example:

```bash
scripts/ops/dr_failback.sh \
  --bucket <bucket> \
  --prefix <prefix> \
  --dr-run-id <dr_run_id> \
  --kubeconfig-dr /tmp/.../k3s.public.yaml \
  --kubeconfig-primary /path/to/primary.kubeconfig \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --namespace jobintel \
  --provider openai \
  --profile cs
```

Controlled dry-run example:

```bash
scripts/ops/dr_failback.sh \
  --bucket <bucket> \
  --prefix <prefix> \
  --dr-run-id <dr_run_id> \
  --kubeconfig-dr /tmp/.../k3s.public.yaml \
  --kubeconfig-primary /path/to/primary.kubeconfig \
  --confirm1 FAILBACK \
  --confirm2 CONFIRM-<dr_run_id> \
  --dry-run
```

---

## G) Rehearsal Workflow (`dr_drill`)

Deterministic drill entrypoint:

```bash
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --auto-promote false \
  --teardown true
```

Flow:
- bringup -> restore (includes control-plane apply) -> validate -> optional promote -> teardown

Teardown verification (when `--teardown=true`):
- DR runner count must return to zero.

Iteration modes (cost-control, deterministic stop boundaries):

> [!WARNING]
> Full drill (`start-at=bringup` with no `--stop-after` and `--teardown=true`) is for release validation only.
> Day-to-day iteration should use `--validate-only` or explicit `--stop-after restore|validate`.
> `dr_drill` now requires `--allow-full-drill` (or `ALLOW_FULL_DRILL=1`) for full drills.

```bash
# 1) Bringup-only, capture kubeconfig into a stable receipt path.
BRINGUP_RUN_ID="m19-dr-bringup-$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${BRINGUP_RUN_ID}" \
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --start-at bringup \
  --stop-after bringup \
  --teardown false \
  --max-attempts 1
# kubeconfig saved at:
# /tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/${BRINGUP_RUN_ID}/kubeconfig.yaml

# 2) Restore-only (DR already up), auto-loading kubeconfig from prior receipt.
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --start-at restore \
  --stop-after restore \
  --receipt-dir /tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/${BRINGUP_RUN_ID} \
  --teardown false

# 3) Validate-only (restore already done), auto-loading kubeconfig from receipt.
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --validate-only \
  --receipt-dir /tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/${BRINGUP_RUN_ID} \
  --teardown false
```

Retry controls:
- `--no-retry` disables retries for all phases.
- `--max-attempts N` caps attempts per phase (validate still bounded by `DR_VALIDATE_MAX_RETRIES + 1`).

Receipts include per-phase execution status (`success|failed|skipped`) and skip reason:
- `<receipt>/phases/*.json`
- `<receipt>/drill.summary.json`

---

## Cost Discipline (Primary Operator Workflow)

For milestone release body template, see `docs/RELEASE_TEMPLATE.md`.

Primary low-cost execution pattern (default for day-to-day operations):
- Bring up DR once, then iterate without recreating infra:
  - `--start-at bringup --stop-after bringup --teardown false`
- Run restore-only while DR infra stays up:
  - `--start-at restore --stop-after restore --receipt-dir <bringup_receipt> --teardown false`
- Iterate validate-only:
  - `--validate-only --receipt-dir <bringup_receipt> --teardown false`
- Final teardown when iteration is complete:
  - `--start-at teardown --teardown true`

Full drills are release-only proof runs:
- Full drill requires `--allow-full-drill` (or `ALLOW_FULL_DRILL=1`) explicitly.
- Use teardown on release proof drills to return runner count to zero.

Reference commands:

```bash
# bringup-only once
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --start-at bringup \
  --stop-after bringup \
  --teardown false

# restore-only using prior receipt-dir kubeconfig
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --start-at restore \
  --stop-after restore \
  --receipt-dir /tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/<bringup_run_id> \
  --teardown false

# validate-only iteration using prior receipt-dir kubeconfig
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --validate-only \
  --receipt-dir /tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/<bringup_run_id> \
  --teardown false

# final teardown after iteration completes
scripts/ops/dr_drill.sh \
  --start-at teardown \
  --teardown true
```

---

## H) Receipts and Proof Artifacts

Local receipts default base:
- `/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/`

Key files for proof:
- `drill.summary.json`
- phase logs under drill receipt dir
- `dr_restore.control_plane.summary.json`
- control-plane fetch/apply receipts:
  - `control-plane/fetch/fetch.summary.env`
  - `control-plane/apply/apply.summary.json`
- failback receipts:
  - `state_transitions.log`
  - `failback.summary.json`

Orchestrator S3 receipts:
- `s3://<receipt_bucket>/<receipt_prefix>/<execution_id>/<phase>.json`
- `s3://<receipt_bucket>/<receipt_prefix>/<execution_id>/codebuild-<action>.json`

---

## Related Docs

- DR semantics: `docs/dr_promote_failback.md`
- DR orchestrator design + approval ops: `docs/dr_orchestrator.md`
- DR module overview: `ops/dr/README.md`
- Orchestrator Terraform module notes: `ops/dr/orchestrator/README.md`
