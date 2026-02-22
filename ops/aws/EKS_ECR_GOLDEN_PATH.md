# EKS + ECR Golden Path (Kubernetes-First)

This is the minimal copy/paste path to run SignalCraft in EKS with a pullable ECR image and IRSA-backed publish.

## Inputs

Set these once:

```bash
export AWS_REGION="us-east-1"
export EKS_CLUSTER_NAME="jobintel-eks"
export JOBINTEL_S3_BUCKET="<bucket>"
export JOBINTEL_S3_PREFIX="jobintel"
export ECR_REPO="jobintel"
export KUBE_CONTEXT="<kubectl-context>"
```

## 1) Bootstrap EKS/IRSA (Terraform)

```bash
terraform -chdir=ops/aws/infra/eks init
terraform -chdir=ops/aws/infra/eks apply \
  -var "region=${AWS_REGION}" \
  -var "s3_bucket=${JOBINTEL_S3_BUCKET}" \
  -var 'subnet_ids=["subnet-aaaa","subnet-bbbb"]'
```

Pull outputs and set kube context:

```bash
terraform -chdir=ops/aws/infra/eks output -raw update_kubeconfig_command
$(terraform -chdir=ops/aws/infra/eks output -raw update_kubeconfig_command)
export JOBINTEL_IRSA_ROLE_ARN="$(terraform -chdir=ops/aws/infra/eks output -raw jobintel_irsa_role_arn)"
```

## 2) Build + push multi-arch image to ECR (+ release metadata)

```bash
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export IMAGE_TAG="$(git rev-parse HEAD)"
scripts/release/build_and_push_ecr.sh
export RELEASE_METADATA="ops/proof/releases/release-${IMAGE_TAG}.json"
export JOBINTEL_IMAGE="$(python3 - <<'PY' "$RELEASE_METADATA"
import json,sys
print(json.load(open(sys.argv[1], "r", encoding="utf-8"))["image_ref_digest"])
PY
)"
```

`scripts/release/build_and_push_ecr.sh` publishes one commit-SHA tag with both `linux/amd64` and `linux/arm64`, then writes release metadata including the digest-pinned image ref.

DR consumers should use this digest ref directly:

```bash
IMAGE_REF="$JOBINTEL_IMAGE" scripts/ops/dr_validate.sh
```

For full DR execution flow and promotion/failback semantics, use:
- `ops/dr/RUNBOOK_DISASTER_RECOVERY.md`
- `docs/dr_promote_failback.md`

## 3) Render/apply manifests without manual YAML edits

```bash
python scripts/k8s_render.py \
  --overlay aws-eks \
  --image "$JOBINTEL_IMAGE" > /tmp/jobintel.yaml
kubectl --context "$KUBE_CONTEXT" apply -f /tmp/jobintel.yaml
```

## 4) Preflight checks (AWS + cluster + repo + bucket)

```bash
python scripts/aws_preflight_eks.py \
  --region "$AWS_REGION" \
  --cluster "$EKS_CLUSTER_NAME" \
  --ecr-repo "$ECR_REPO" \
  --bucket "$JOBINTEL_S3_BUCKET" \
  --kube-context "$KUBE_CONTEXT"
```

## 5) Validate image pull from EKS

```bash
kubectl --context "$KUBE_CONTEXT" -n jobintel get pods
POD_NAME="$(kubectl --context "$KUBE_CONTEXT" -n jobintel get pods -l app.kubernetes.io/name=jobintel -o jsonpath='{.items[0].metadata.name}')"
kubectl --context "$KUBE_CONTEXT" -n jobintel describe pod "$POD_NAME" | rg -n "Image:|Image ID:|ImagePullBackOff|ErrImagePull"
```

Expected: no `ImagePullBackOff` / `ErrImagePull`.

## IAM notes

- Operator push permissions (AWS CLI user/role): `ecr:CreateRepository` (optional), `ecr:GetAuthorizationToken`, `ecr:PutImage`, upload-layer actions.
- EKS node pull permissions (node IAM role, not IRSA): `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchCheckLayerAvailability`.
- Runtime publish permissions (IRSA role): S3 publish/list actions documented in `ops/aws/README.md`.

## Completion rule

Milestone item “EKS can pull image (ECR golden path documented + working)” is checked only after a human run shows:
- preflight OK,
- pod starts with the ECR image,
- no `ImagePullBackOff`.
