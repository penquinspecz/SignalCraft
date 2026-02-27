# M19B IAM `ListRolePolicies` Least-Privilege Fix (2026-02-27)

## Summary

- **Goal:** clear DR bringup failure caused by missing IAM permission in orchestrator CodeBuild role.
- **CodeBuild project:** `signalcraft-dr-orchestrator-dr-infra`
- **CodeBuild service role:** `arn:aws:iam::048622080012:role/signalcraft-dr-orchestrator-codebuild-role`
- **Execution ARN (post-fix rerun):** `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T040524Z`

## Root Cause

Terraform in CodeBuild was creating `aws_iam_role.dr_runner_ssm` (`jobintel-dr-runner-ssm-role`) and provider read-path required:

- `iam:ListRolePolicies` on `role/jobintel-dr-runner-ssm-role`

Before fix, CodeBuild failed in BUILD phase with:

- `AccessDenied ... not authorized to perform: iam:ListRolePolicies on resource: role jobintel-dr-runner-ssm-role`

## IAM Change (Least Privilege)

Updated orchestrator-managed CodeBuild policy in `ops/dr/orchestrator/main.tf` to add only:

```hcl
{
  Sid      = "TerraformIamRoleInlinePolicyRead"
  Effect   = "Allow"
  Action   = ["iam:ListRolePolicies"]
  Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role"
}
```

Why this is least-privilege:

- single IAM read action
- scoped to one concrete role ARN
- no `iam:*` expansion and no new wildcard resource grant

## Validation / Deployment

- `terraform -chdir=ops/dr/orchestrator validate` -> PASS
- `terraform -chdir=ops/dr/orchestrator plan ...` -> only `aws_iam_role_policy.codebuild` in-place update
- `terraform -chdir=ops/dr/orchestrator apply` -> `0 added, 1 changed, 0 destroyed`

## Rehearsal Result After Fix

- Re-ran DR orchestrator with `force_run=true` execution name `m19b-success-true-20260227T040524Z`
- `DOWNLOAD_SOURCE` succeeded (YAML parse blocker remains resolved)
- `ListRolePolicies` blocker cleared
- Workflow moved to a **new blocker**:
  - `iam:ListAttachedRolePolicies` denied on `jobintel-dr-runner-ssm-role`

Status: success-path still **not complete**; moved forward to next least-privilege gap.

## Artifacts

- `docs/proof/m19b-orchestrator-success-true-describe-20260227T040524Z.json`
- `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T040524Z.json`
- `docs/proof/m19b-codebuild-batch-get-builds-20260227T040524Z.json`
- `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T040524Z.json`
- `docs/proof/receipts-m19b-success-true-20260227T040524Z/check_health.json`
- `docs/proof/receipts-m19b-success-true-20260227T040524Z/notify.json`
