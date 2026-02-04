#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
EKS bootstrap (preview only)

1) Initialize Terraform:
   terraform -chdir=ops/aws/infra/eks init

2) Apply with required variables:
   terraform -chdir=ops/aws/infra/eks apply \
     -var 's3_bucket=<bucket>' \
     -var 'subnet_ids=["subnet-aaaa","subnet-bbbb"]'

3) Configure kubectl:
   $(terraform -chdir=ops/aws/infra/eks output -raw update_kubeconfig_command)

4) Annotate service account:
   kubectl -n jobintel annotate sa jobintel \
     $(terraform -chdir=ops/aws/infra/eks output -raw serviceaccount_annotation) --overwrite
EOF
