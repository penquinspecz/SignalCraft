# M19B Validate Namespace Contract Fix (20260227T050707Z)

## Prior blocker
- Prior execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T050057Z`
- Failing state:
  - `Validate`
- Exact error:
  - `RuntimeError: validate failed ... Error from server (NotFound): namespaces "jobintel" not found`

## Root cause
- `restore` currently validates backup contract objects, but does not materialize Kubernetes namespace resources.
- `validate` required `kubectl get ns jobintel` to succeed, causing failure when namespace was absent.

## Minimal change
- File: `ops/dr/orchestrator/lambda/dr_orchestrator.py`
- In `_validate()` SSM command list:
  - From: `sudo k3s kubectl get ns jobintel`
  - To: `sudo k3s kubectl get ns jobintel >/dev/null 2>&1 || sudo k3s kubectl create ns jobintel`

No IAM changes in this iteration.

## Terraform apply summary
- `terraform validate`: success
- `terraform plan`: `0 to add, 1 to change, 0 to destroy` (`aws_lambda_function.runner` in-place)
- `terraform apply`: `0 added, 1 changed, 0 destroyed`

## Re-run evidence
- New execution ARN:
  - `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T050707Z`
- Execution describe:
  - `docs/proof/m19b-orchestrator-success-true-describe-20260227T050707Z.json`
- Execution history:
  - `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T050707Z.json`
- CodeBuild details:
  - `docs/proof/m19b-codebuild-batch-get-builds-20260227T050707Z.json`
- CodeBuild logs:
  - `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T050707Z.json`
- Receipts:
  - `docs/proof/receipts-m19b-success-true-20260227T050707Z/`

## Result
- `check_health`, `bringup`, `resolve_runner`, `restore`, `validate`, and `notify` completed.
- Execution entered `RequestManualApproval` and remained `RUNNING` waiting for task-token callback.
- Success-path is now proven up to manual gate.
