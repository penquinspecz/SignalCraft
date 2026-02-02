# Kubernetes CronJob (JobIntel)

This directory contains a minimal, Kubernetes-native CronJob shape for running JobIntel daily.
It is intentionally plain YAML (no Helm).

## Apply

```bash
kubectl create namespace jobintel
kubectl apply -f ops/k8s/configmap.yaml
kubectl apply -f ops/k8s/cronjob.yaml
```

## Required secrets

Create a secret named `jobintel-secrets` with the following keys (use only what you need):
- `JOBINTEL_S3_BUCKET`: target bucket for publish
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `DISCORD_WEBHOOK_URL`: optional alerts
- `OPENAI_API_KEY`: optional AI features

Notes:
- Secrets-based auth is the primary example.
- IRSA / workload identity is supported by Kubernetes, but not assumed here.

## Dry-run / deterministic mode

To run without AWS calls:
- Set `PUBLISH_S3_DRY_RUN=1` (or `PUBLISH_S3=0`) in the ConfigMap or at runtime.
- CronJob args already include `--snapshot-only` for offline determinism.

Example override:
```bash
kubectl set env cronjob/jobintel-daily -n jobintel PUBLISH_S3_DRY_RUN=1
```

## Verification

After a run, verify published artifacts (requires credentials):
```bash
python scripts/verify_published_s3.py \
  --bucket "$JOBINTEL_S3_BUCKET" \
  --run-id <run_id> \
  --verify-latest
```

## Storage notes

The CronJob uses `emptyDir` for `/app/data` and `/app/state` by default.
For persistence across runs, replace these with PVCs or a CSI-backed volume.
