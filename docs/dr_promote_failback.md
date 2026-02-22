# DR Promote and Failback Semantics

Canonical execution flow lives in `ops/dr/RUNBOOK_DISASTER_RECOVERY.md`.
Use this document for semantic intent; use the runbook for end-to-end operator commands.

## Purpose

Define deterministic, Kubernetes-native DR semantics for:
- what `promote` means today (batch mode)
- what it will mean later (UI/API endpoint mode)
- how failback is executed safely

Auto-promote is out of scope by design.

## Deterministic Drill Command

`scripts/ops/dr_drill.sh` is the deterministic non-production rehearsal entrypoint:

- bringup -> restore -> validate -> promote (optional) -> teardown
- creates a timestamped receipt bundle
- records git SHA, image ref, AWS account/region, per-phase logs, and `drill.summary.json`
- retries each phase up to 3 times with one minimal repair attempt per phase

Required input:

```bash
scripts/ops/dr_drill.sh --backup-uri s3://<bucket>/<prefix>/backups/<backup_id>
```

Common release-safe invocation:

```bash
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --auto-promote false \
  --teardown true
```

Equivalent make target:

```bash
make dr-drill BACKUP_URI=s3://<bucket>/<prefix>/backups/<backup_id> \
  IMAGE_REF=<account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest>
```

## Control Plane Bundle Parity

DR now restores not only infra/data artifacts but also control-plane config parity:
- candidates
- alerts
- providers
- scoring

Publish from primary:

```bash
scripts/control_plane/publish_bundle.sh \
  --bucket <bucket> \
  --prefix <prefix> \
  --image-ref-digest <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest>
```

Restore path applies same bundle to DR before validate:

```bash
scripts/ops/dr_restore.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --kubeconfig /tmp/.../k3s.public.yaml \
  --namespace jobintel
```

Receipts include:
- `dr_restore.control_plane.summary.json` (`bundle_uri`, `bundle_sha256`, `candidate_count`, `alert_count`, `provider_count`, `scoring_count`)
- `control-plane/fetch/fetch.summary.env`
- `control-plane/apply/apply.summary.json`

## Promote in Batch Mode (Current)

In batch mode, there is no live read endpoint to switch. Promotion means:

1. DR validation is complete and receipted.
2. Operators explicitly approve promotion.
3. DR-produced publish pointers/artifacts are treated as canonical for downstream batch consumers.
4. Primary batch schedulers remain paused until failback criteria are met.

What promotion does **not** mean today:
- no DNS or API endpoint cutover
- no automatic traffic switching

Promotion guardrail in `dr_drill.sh`:
- Promotion runs only when both flags are true: `--auto-promote=true` and `--allow-promote-bypass=true`.
- Without both flags, promotion is skipped or rejected safely.

## Promote in UI/API Mode (Future)

When UI/API serving is introduced, promotion will additionally mean:

1. Endpoint ownership transfer (for example Route53/DNS or edge routing) to DR control plane.
2. Serving stack health verification on DR endpoint.
3. Read/write contract verification for API surface.
4. Explicit declaration of active region/site in run metadata and ops dashboard.

Batch publish correctness checks remain required even after endpoint cutover exists.

## Failback Safety Contract

Failback must be deterministic and receipted:

1. Freeze writes in both directions (no split-brain publishing).
2. Capture current pointers + run ids on active DR side.
3. Verify published artifacts and pointers (`scripts/verify_published_s3.py`).
4. Reconcile divergence (`scripts/compare_run_artifacts.py`) and resolve conflicts.
5. Re-enable primary publish path.
6. Switch canonical pointers back to primary.
7. Monitor freshness/correctness alarms through one full batch cycle.

## Failback Command (Implemented)

`scripts/ops/dr_failback.sh` now executes actual failback mechanics with hard safety gates:

- preflight: primary + DR cluster reachability
- precondition: DR promoted pointer check (`state/last_success.json` + provider pointer)
- freeze DR scheduling + wait for no in-flight DR jobs
- optional artifact sync
- demote DR publish config
- optional primary restore contract check
- run primary validation job + capture new run id
- verify no divergence (`verify_published_s3.py` + `compare_run_artifacts.py`)
- teardown DR infra (default on)

### Interactive failback

```bash
scripts/ops/dr_failback.sh \
  --bucket <bucket> \
  --prefix jobintel \
  --dr-run-id <dr_run_id> \
  --kubeconfig-dr /tmp/.../k3s.public.yaml \
  --kubeconfig-primary /path/to/primary.kubeconfig \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --namespace jobintel \
  --provider openai \
  --profile cs
```

### Non-interactive confirmations (for controlled automation)

```bash
scripts/ops/dr_failback.sh \
  --bucket <bucket> \
  --prefix jobintel \
  --dr-run-id <dr_run_id> \
  --kubeconfig-dr /tmp/.../k3s.public.yaml \
  --kubeconfig-primary /path/to/primary.kubeconfig \
  --confirm1 FAILBACK \
  --confirm2 CONFIRM-<dr_run_id>
```

### Controlled drill mode

Use `--dry-run` to test state-transition and receipt plumbing without mutating clusters or AWS resources:

```bash
scripts/ops/dr_failback.sh \
  --bucket <bucket> \
  --prefix jobintel \
  --dr-run-id <dr_run_id> \
  --kubeconfig-dr /tmp/.../k3s.public.yaml \
  --kubeconfig-primary /path/to/primary.kubeconfig \
  --confirm1 FAILBACK \
  --confirm2 CONFIRM-<dr_run_id> \
  --dry-run
```

Receipts are written under `/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/m19-dr-failback-<timestamp>/`, including:

- `state_transitions.log`
- `failback.summary.json`
- phase command logs and verification outputs

## Minimum Promote Receipt Fields

- operator identity
- approval timestamp (UTC)
- ticket/change id
- execution id (Step Functions)
- instance id / cluster identity
- chosen canonical run id
- receipt object prefix

## Minimum Failback Receipt Fields

- freeze start/end timestamps
- pre/post pointers on DR and primary
- artifact verification result
- divergence diff summary
- switchback timestamp
- first successful post-failback publish run id
