# M19B IAM Fix Proof: ListInstanceProfilesForRole (20260227T042825Z)

## What failed before
- Prior execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T041537Z`
- Failing Step Functions state:
  - `BringupInfra`
- Exact AWS error string (from CodeBuild CloudWatch logs):
  - `Error: deleting IAM Role (jobintel-dr-runner-ssm-role): reading IAM Instance Profiles for Role (jobintel-dr-runner-ssm-role): operation error IAM: ListInstanceProfilesForRole, https response error StatusCode: 403, RequestID: 0c7cdda7-2500-4797-a240-d6bcee414fed, api error AccessDenied: User: arn:aws:sts::048622080012:assumed-role/signalcraft-dr-orchestrator-codebuild-role/AWSCodeBuild-7f19826a-be12-4773-8113-02977889c54a is not authorized to perform: iam:ListInstanceProfilesForRole on resource: role jobintel-dr-runner-ssm-role because no identity-based policy allows the iam:ListInstanceProfilesForRole action`
- Evidence file:
  - `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T041537Z.json`

## Minimal IAM diff
- File: `ops/dr/orchestrator/main.tf`
- Added one statement to `aws_iam_role_policy.codebuild`:
  - `Sid = "TerraformIamRoleInstanceProfileRead"`
  - `Action = ["iam:ListInstanceProfilesForRole"]`
  - `Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role"`
- No additional IAM actions added.

## Resource scope decision
- `Resource "*"` was **not** required.
- Scoped role ARN grant was accepted and effective; subsequent run progressed beyond the previous `iam:ListInstanceProfilesForRole` failure.

## Terraform plan/apply summary
- `terraform validate`: success
- `terraform plan`: `Plan: 0 to add, 1 to change, 0 to destroy`
- `terraform apply`: `Apply complete! Resources: 0 added, 1 changed, 0 destroyed.`

## Re-run evidence
- New execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T042825Z`
- Describe JSON:
  - `docs/proof/m19b-orchestrator-success-true-describe-20260227T042825Z.json`
- Execution history JSON:
  - `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T042825Z.json`
- CodeBuild details:
  - `docs/proof/m19b-codebuild-batch-get-builds-20260227T042825Z.json`
- CodeBuild logs:
  - `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T042825Z.json`
- Receipts copied:
  - `docs/proof/receipts-m19b-success-true-20260227T042825Z/`

## Result
- The `iam:ListInstanceProfilesForRole` blocker is cleared.
- Workflow progressed further in `BringupInfra` and hit a new least-privilege blocker:
  - `AccessDenied ... iam:TagInstanceProfile ... arn:aws:iam::048622080012:instance-profile/jobintel-dr-runner-instance-profile`
- Exact new error appears in:
  - `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T042825Z.json`
