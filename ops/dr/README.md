# Cold-Standby DR (On-Demand)

This DR path is intentionally **cold-standby** and **teardown-friendly**.
Canonical operator runbook: `ops/dr/RUNBOOK_DISASTER_RECOVERY.md`.

## Architecture (default)

- DR runner: single ARM EC2 instance with k3s server.
- Backups and run artifacts: S3.
- Control plane: Terraform + shell scripts in this repo.

Why this default:
- Lower steady-state cost than always-on EKS.
- Fast enough for restore-and-validate drills.
- Deterministic and code-defined lifecycle.

## Cost posture

- Normal mode: S3 storage only.
- DR event mode: temporary EC2 runtime + transfer bandwidth + short-lived control actions.

## Golden path

```bash
make dr-plan
make dr-apply
BACKUP_URI=s3://<bucket>/<prefix>/backups/<backup_id> make dr-validate
CONFIRM_DESTROY=1 make dr-destroy
```

Full deterministic rehearsal entrypoint (recommended):

```bash
scripts/ops/dr_drill.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --image-ref <account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  --auto-promote false \
  --teardown true
```

Release-safe validation (digest-pinned image, preferred):

```bash
IMAGE_REF=<account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest> \
  RUN_JOB=1 NAMESPACE=jobintel scripts/ops/dr_validate.sh
```

Tag-based image refs are accepted for development only:

```bash
IMAGE_REF=<account>.dkr.ecr.us-east-1.amazonaws.com/jobintel:<tag> \
  RUN_JOB=1 NAMESPACE=jobintel scripts/ops/dr_validate.sh
```

Milestone 4 deterministic plan bundle:

```bash
python scripts/ops/prove_it_m4.py \
  --plan \
  --run-id m4-dr-plan \
  --output-dir ops/proof/bundles \
  --aws-region us-east-1 \
  --backup-bucket <bucket> \
  --backup-prefix <prefix>/backups/m4-dr-plan \
  --backup-uri s3://<bucket>/<prefix>/backups/m4-dr-plan
```

## Restore contract

Required backup layout:

- `s3://<bucket>/<prefix>/backups/<backup_id>/metadata.json`
- `s3://<bucket>/<prefix>/backups/<backup_id>/state.tar.zst`
- `s3://<bucket>/<prefix>/backups/<backup_id>/manifests.tar.zst`

Validation command:

```bash
scripts/ops/dr_restore.sh \
  --backup-uri s3://<bucket>/<prefix>/backups/<backup_id> \
  --kubeconfig /tmp/.../k3s.public.yaml \
  --namespace jobintel
```

## Notes

- This scaffold is cloud-specific in implementation, but Kubernetes-native in runtime shape (k3s + CronJob).
- EKS can still be used as an explicit alternative path; this DR baseline does not require it.
- DR rehearsal runbook: `ops/dr/RUNBOOK_DISASTER_RECOVERY.md`.
- DR orchestrator (auto-detect -> auto-validate -> manual promote): `docs/dr_orchestrator.md` and `ops/dr/orchestrator/`.
