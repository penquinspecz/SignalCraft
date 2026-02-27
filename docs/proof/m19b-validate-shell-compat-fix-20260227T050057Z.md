# M19B Validate Shell Compatibility Fix (20260227T050057Z)

## Prior execution and root cause
- Prior execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T045044Z`
- Failing state:
  - `Validate`
- Exact failure:
  - `set: Illegal option -o pipefail`
- Cause:
  - `AWS-RunShellScript` executes under `/bin/sh`; `pipefail` is a bash-only option.

## Minimal change made
- File: `ops/dr/orchestrator/lambda/dr_orchestrator.py`
- In `_validate()` SSM commands list:
  - `set -euo pipefail` -> `set -eu`

No IAM or state-machine policy change was made in this iteration.

## Terraform apply summary
- `terraform validate`: success
- `terraform plan`: `0 to add, 1 to change, 0 to destroy` (`aws_lambda_function.runner` in-place)
- `terraform apply`: `0 added, 1 changed, 0 destroyed`

## Re-run evidence
- New execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T050057Z`
- Execution describe:
  - `docs/proof/m19b-orchestrator-success-true-describe-20260227T050057Z.json`
- Execution history:
  - `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T050057Z.json`
- CodeBuild details:
  - `docs/proof/m19b-codebuild-batch-get-builds-20260227T050057Z.json`
- CodeBuild logs:
  - `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T050057Z.json`
- Receipts copied:
  - `docs/proof/receipts-m19b-success-true-20260227T050057Z/`

## Result and next blocker
- Progress improved:
  - `BringupInfra` succeeded
  - `ResolveRunner` succeeded
  - `Restore` succeeded
  - `Validate` executed with shell compatibility fixed
- New blocker (non-IAM):
  - `RuntimeError: validate failed ... Error from server (NotFound): namespaces "jobintel" not found`
- No `request_manual_approval` state reached yet.
