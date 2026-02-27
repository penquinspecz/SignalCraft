# M19B IAM Fix Proof: TagInstanceProfile (20260227T044403Z)

## Prior blocker confirmation
- Prior execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T042825Z`
- Failing state:
  - `BringupInfra`
- Exact AccessDenied (principal + action + resource):
  - `Error: creating IAM Instance Profile (jobintel-dr-runner-instance-profile): operation error IAM: CreateInstanceProfile, https response error StatusCode: 403, RequestID: 3b4bfb50-c67c-45b9-a096-2c10bc6e82c4, api error AccessDenied: User: arn:aws:sts::048622080012:assumed-role/signalcraft-dr-orchestrator-codebuild-role/AWSCodeBuild-697e286a-b962-4582-a71d-d3204d222b96 is not authorized to perform: iam:TagInstanceProfile on resource: arn:aws:iam::048622080012:instance-profile/jobintel-dr-runner-instance-profile because no identity-based policy allows the iam:TagInstanceProfile action`
- Evidence source:
  - `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T042825Z.json`

## Minimal IAM diff
File: `ops/dr/orchestrator/main.tf`
- Added one statement to `aws_iam_role_policy.codebuild`:
  - `Action = ["iam:TagInstanceProfile"]`
  - `Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:instance-profile/jobintel-dr-runner-instance-profile"`
- No additional IAM actions added.

## Terraform summary
- `terraform validate`: success
- `terraform plan`: `Plan: 0 to add, 1 to change, 0 to destroy`
- `terraform apply`: `Apply complete! Resources: 0 added, 1 changed, 0 destroyed.`

## Re-run result
- New execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T044403Z`
- CodeBuild bringup build:
  - `signalcraft-dr-orchestrator-dr-infra:de383d1d-118e-4dd7-8c89-8680b0252527`
  - `BuildStatus: SUCCEEDED`
- Workflow progressed beyond prior IAM blocker. New failure is not AccessDenied:
  - `States.Runtime` in `BringupInfra` due missing JSONPath in ResultSelector/format expression:
  - `The JsonPath argument for the field '$.receipt_bucket' could not be found in the input ...`

## Exported artifacts
- `docs/proof/m19b-orchestrator-success-true-describe-20260227T044403Z.json`
- `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T044403Z.json`
- `docs/proof/m19b-codebuild-batch-get-builds-20260227T044403Z.json`
- `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T044403Z.json`
- `docs/proof/receipts-m19b-success-true-20260227T044403Z/check_health.json`
- `docs/proof/receipts-m19b-success-true-20260227T044403Z/codebuild-bringup.json`
