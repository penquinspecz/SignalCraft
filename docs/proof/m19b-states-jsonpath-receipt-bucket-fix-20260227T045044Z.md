# M19B Step Functions JSONPath Fix Proof: receipt_bucket wiring (20260227T045044Z)

## Prior failure context
- Failing execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T044403Z`
- Failing state:
  - `BringupInfra`
- Runtime error:
  - `States.Runtime ... The JsonPath argument for the field '$.receipt_bucket' could not be found in the input ...`

## Failing JSON snippet (before fix)
Source: `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T044403Z.json`

- `BringupInfra` state input included `receipt_bucket` and `receipt_prefix` at the top level:
```json
{
  "receipt_bucket": "jobintel-prod1",
  "receipt_prefix": "jobintel/dr-orchestrator/receipts",
  "current_phase": {"name": "bringup"}
}
```

- But the Task result consumed by `ResultSelector` was CodeBuild output rooted at `Build`:
```json
{
  "Build": {
    "BuildStatus": "SUCCEEDED",
    "Id": "signalcraft-dr-orchestrator-dr-infra:de383d1d-118e-4dd7-8c89-8680b0252527"
  }
}
```

## Expected vs actual structure
- Expected by failing JSONPath in `BringupInfra.ResultSelector`:
  - `$.receipt_bucket` and `$.receipt_prefix` exist in the selector input
- Actual selector input:
  - only Task result object (`Build`, SDK metadata), no top-level `receipt_bucket`

Therefore `$.receipt_bucket` was invalid in that selector scope.

## Minimal state-machine diff
File: `ops/dr/orchestrator/main.tf` (`aws_sfn_state_machine.dr_orchestrator` -> `BringupInfra` -> `ResultSelector`)

```diff
- "receipt_uri.$" = "States.Format('s3://{}/{}/{}/codebuild-bringup.json', $.receipt_bucket, $.receipt_prefix, $$.Execution.Name)"
+ "receipt_uri.$" = "States.Format('s3://{}/{}/{}/codebuild-bringup.json', $$.Execution.Input.receipt_bucket, $$.Execution.Input.receipt_prefix, $$.Execution.Name)"
```

## Terraform apply summary
- `terraform validate`: success
- `terraform plan`: `0 to add, 1 to change, 0 to destroy` (`aws_sfn_state_machine.dr_orchestrator` in-place)
- `terraform apply`: `0 added, 1 changed, 0 destroyed`

## Re-run result after fix
- New execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T045044Z`
- Progression observed:
  - `BringupInfra` succeeded
  - `ResolveRunner` succeeded
  - `Restore` succeeded
  - `Validate` reached and failed

## Next blocker
- New failure is no longer JSONPath wiring and no longer IAM in bringup.
- Failing state/action:
  - `Validate` Lambda task
- Exact failure reason excerpt:
  - `validate failed: ... /_script.sh: 1: set: Illegal option -o pipefail ... receipt=s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260227T045044Z/validate.json`

## Artifacts
- `docs/proof/m19b-orchestrator-success-true-describe-20260227T045044Z.json`
- `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T045044Z.json`
- `docs/proof/receipts-m19b-success-true-20260227T045044Z/check_health.json`
- `docs/proof/receipts-m19b-success-true-20260227T045044Z/codebuild-bringup.json`
- `docs/proof/receipts-m19b-success-true-20260227T045044Z/resolve_runner.json`
- `docs/proof/receipts-m19b-success-true-20260227T045044Z/restore.json`
- `docs/proof/receipts-m19b-success-true-20260227T045044Z/validate.json`
- `docs/proof/receipts-m19b-success-true-20260227T045044Z/notify.json`
