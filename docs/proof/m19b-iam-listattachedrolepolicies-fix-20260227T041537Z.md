# M19B IAM Fix Proof: ListAttachedRolePolicies (20260227T041537Z)

## Summary
- Prior failure (execution `m19b-success-true-20260227T040524Z`) was:
  - `AccessDenied ... iam:ListAttachedRolePolicies ... role jobintel-dr-runner-ssm-role`
- Minimal fix applied in orchestrator CodeBuild role policy:
  - Added `iam:ListAttachedRolePolicies`
  - Scoped resource to `arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role`
- Re-applied orchestrator Terraform with a single in-place change to `aws_iam_role_policy.codebuild`.

## IAM Diff (Least Privilege)
File: `ops/dr/orchestrator/main.tf`
- Added statement:
  - `Sid = "TerraformIamRoleAttachedPolicyRead"`
  - `Action = ["iam:ListAttachedRolePolicies"]`
  - `Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role"`

No wildcard IAM action was introduced.

## Why This Permission Is Required
Terraform in DR bringup manages runner IAM resources in `ops/dr/terraform/main.tf`, including:
- `aws_iam_role.dr_runner_ssm`
- `aws_iam_role_policy_attachment.dr_runner_ssm_core`
- `aws_iam_instance_profile.dr_runner`

During reconciliation/deletion of the runner role, the AWS provider reads attached managed policies, which requires `iam:ListAttachedRolePolicies` on the runner role.

## Rerun Evidence
- New execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T041537Z`
- Execution describe:
  - `docs/proof/m19b-orchestrator-success-true-describe-20260227T041537Z.json`
- Execution history:
  - `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T041537Z.json`
- CodeBuild build details:
  - `docs/proof/m19b-codebuild-batch-get-builds-20260227T041537Z.json`
- CodeBuild CloudWatch log events:
  - `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T041537Z.json`
- Receipts copied locally:
  - `docs/proof/receipts-m19b-success-true-20260227T041537Z/`

## Result
- `iam:ListAttachedRolePolicies` blocker is resolved.
- Workflow progressed further and now fails on next least-privilege gap:
  - `AccessDenied ... iam:ListInstanceProfilesForRole ... role jobintel-dr-runner-ssm-role`
- Exact new error captured in:
  - `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T041537Z.json`
