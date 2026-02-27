# M19B Post-Success Teardown Proof

- Timestamp (UTC): 2026-02-27T05:21:46Z
- Execution ARN (stopped at manual gate): `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T050707Z`

## Pre-Teardown State (why teardown was run)

- `Purpose=jobintel-dr` EC2 instances: 1 running (`i-0313e98010ecef6e0`, `jobintel-dr-runner`)
- CodeBuild in-progress builds for `signalcraft-dr-orchestrator-dr-infra`: 0
- S3 receipt prefix objects present: 37 (receipt artifacts)

Evidence:
- `docs/proof/m19b-post-success-ec2-purpose-jobintel-dr-20260227T051916Z.json`
- `docs/proof/m19b-post-success-codebuild-list-20260227T051916Z.json`
- `docs/proof/m19b-post-success-codebuild-batch-20260227T051916Z.json`
- `docs/proof/m19b-post-success-s3-prefix-objects-20260227T051916Z.json`
- `docs/proof/m19b-post-success-eks-list-20260227T051916Z.json`
- `docs/proof/m19b-post-success-eks-describe-20260227T051916Z.jsonl`
- `docs/proof/m19b-post-success-elbv2-all-20260227T051916Z.json`

## Teardown Action

Deterministic teardown path executed:
- Command path: `scripts/ops/dr_teardown.sh`
- Mode: `CONFIRM_DESTROY=1`
- Receipt bundle: `docs/proof/receipts-m19b-post-success-teardown-20260227T052010Z/`

Terraform apply summary from teardown receipts:
- `Apply complete! Resources: 0 added, 0 changed, 5 destroyed.`

## Post-Teardown Steady State

- `Purpose=jobintel-dr` EC2 instances: 0 running (none)
- CodeBuild in-progress builds for DR infra project: 0
- DR-tagged ELBv2 load balancers (`Purpose=jobintel-dr`): 0
- EKS clusters: `jobintel-eks` remains `ACTIVE` (created 2026-02-04, no tags; treated as pre-existing/non-DR-run artifact)
- Receipt prefix objects remain as evidence (37 objects)

Evidence:
- `docs/proof/m19b-post-teardown-ec2-purpose-jobintel-dr-20260227T052146Z.json`
- `docs/proof/m19b-post-teardown-codebuild-list-20260227T052146Z.json`
- `docs/proof/m19b-post-teardown-codebuild-batch-20260227T052146Z.json`
- `docs/proof/m19b-post-teardown-elbv2-all-20260227T052146Z.json`
- `docs/proof/m19b-post-teardown-eks-list-20260227T052146Z.json`
- `docs/proof/m19b-post-teardown-eks-describe-20260227T052146Z.jsonl`
- `docs/proof/m19b-post-teardown-s3-prefix-objects-20260227T052146Z.json`
