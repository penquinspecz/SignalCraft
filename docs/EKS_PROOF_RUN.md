# EKS Proof Run (Golden Path)

This is the single, copy/paste path to produce proof receipts for Milestone 2.
It assumes you have valid AWS credentials and a target S3 bucket.

## 0) Prereqs

- Terraform >= 1.4
- `kubectl` configured
- AWS credentials with EKS + IAM + S3 access
- An S3 bucket for publish (S3-compatible object store)

## 1) Terraform apply (EKS + IRSA)

```bash
cd ops/aws/infra/eks
terraform init
terraform apply \
  -var 's3_bucket=<bucket>' \
  -var 'subnet_ids=["subnet-aaaa","subnet-bbbb"]'
```

## 2) Configure kubectl (from Terraform output)

```bash
terraform -chdir=ops/aws/infra/eks output -raw update_kubeconfig_command
```

Copy/paste the command it prints, then select the context:

```bash
kubectl config use-context <your-eks-context>
```

## 3) Render + apply manifests (IRSA wired)

```bash
export JOBINTEL_IRSA_ROLE_ARN="$(terraform -chdir=ops/aws/infra/eks output -raw jobintel_irsa_role_arn)"
export JOBINTEL_S3_BUCKET=<bucket>

python scripts/k8s_render.py --overlay aws-eks > /tmp/jobintel.yaml
kubectl apply -f /tmp/jobintel.yaml
```

Optional sanity check:

```bash
kubectl -n jobintel auth can-i create pods --as=system:serviceaccount:jobintel:jobintel
```

## 4) Create secrets (no secrets in repo)

```bash
kubectl -n jobintel create secret generic jobintel-secrets \
  --from-literal=JOBINTEL_S3_BUCKET="$JOBINTEL_S3_BUCKET" \
  --from-literal=DISCORD_WEBHOOK_URL=... \
  --from-literal=OPENAI_API_KEY=...
```

## 5) Run one-off job from the CronJob template

```bash
kubectl delete job -n jobintel jobintel-manual-$(date +%Y%m%d) --ignore-not-found
kubectl create job -n jobintel --from=cronjob/jobintel-daily jobintel-manual-$(date +%Y%m%d)
kubectl logs -n jobintel job/jobintel-manual-$(date +%Y%m%d)
```

You must see a log line like:

```
JOBINTEL_RUN_ID=<run_id>
```

## 6) Capture proof JSON (uses logs if run_id omitted)

```bash
python scripts/prove_cloud_run.py \
  --bucket "$JOBINTEL_S3_BUCKET" \
  --prefix jobintel \
  --namespace jobintel \
  --job-name jobintel-manual-$(date +%Y%m%d) \
  --kube-context <your-eks-context>
```

This writes the local proof receipt:

```
state/proofs/<run_id>.json
```

## 7) Verify latest keys

```bash
python scripts/verify_published_s3.py \
  --bucket "$JOBINTEL_S3_BUCKET" \
  --run-id <run_id> \
  --verify-latest
```
