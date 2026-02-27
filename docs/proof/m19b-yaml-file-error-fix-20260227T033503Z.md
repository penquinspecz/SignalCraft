# M19B CodeBuild `YAML_FILE_ERROR` Fix Proof (2026-02-27)

## Scope

Fix DR orchestrator bringup failure:

- **Old failure:** `YAML_FILE_ERROR` / `did not find expected key at line 15`
- **Location:** CodeBuild project `signalcraft-dr-orchestrator-dr-infra`
- **Execution:** `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T032245Z`

## Root Cause

The CodeBuild project uses an **inline** buildspec (`source.type=NO_SOURCE`), rendered from `ops/dr/orchestrator/buildspec-dr-infra.yml` via Terraform.

The failing YAML section at/after line 15 was:

```yaml
  build:
    commands:
      - set -euo pipefail
      - : "${ACTION:?ACTION is required}"
```

`yaml.safe_load` fails on the unquoted command beginning with `:`:

- parser error points to line 16, column 9 (`- : "${ACTION:?ACTION is required}"`)
- CodeBuild surfaced this as `line 15` in `YAML_FILE_ERROR` context

## Minimal Fix

1. Quote `:`-prefixed shell commands in `ops/dr/orchestrator/buildspec-dr-infra.yml`.
2. Add deterministic Terraform-side YAML validation/rendering:
   - `local.dr_infra_buildspec = yamlencode(yamldecode(file("${path.module}/buildspec-dr-infra.yml")))`
   - use `local.dr_infra_buildspec` for CodeBuild `source.buildspec`.

This keeps fix scope small and fails closed on invalid YAML before deployment.

## Deployment

Applied orchestrator Terraform in `ops/dr/orchestrator` (in-place update of CodeBuild project buildspec only).

## Proof: Before vs After

### Before (reproduced failure)

- Step Functions execution: `m19b-success-true-20260227T032245Z`
- Build ID: `signalcraft-dr-orchestrator-dr-infra:28fb7bd0-c651-4865-babe-388c4c7da8d1`
- Failed phase: `DOWNLOAD_SOURCE`
- Status code: `YAML_FILE_ERROR`
- Message: `did not find expected key at line 15`

Artifacts:

- `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T032245Z.json`
- `docs/proof/m19b-codebuild-batch-get-builds-20260227T032245Z.json`
- `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T032245Z.json`

### After (post-fix run)

- Step Functions execution: `m19b-success-true-20260227T033503Z`
- Build ID: `signalcraft-dr-orchestrator-dr-infra:64809a06-b359-42f6-a2bd-ea3c91aebc74`
- `DOWNLOAD_SOURCE`: **SUCCEEDED**
- `YAML_FILE_ERROR`: **not present**
- New failure: `BUILD` / `COMMAND_EXECUTION_ERROR` caused by IAM permission:
  - `AccessDenied` on `iam:ListRolePolicies` for role `jobintel-dr-runner-ssm-role`

Artifacts:

- `docs/proof/m19b-orchestrator-success-true-describe-20260227T033503Z.json`
- `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T033503Z.json`
- `docs/proof/m19b-codebuild-batch-get-builds-20260227T033503Z.json`
- `docs/proof/m19b-codebuild-cloudwatch-log-events-20260227T033503Z.json`
- `docs/proof/receipts-m19b-success-true-20260227T033503Z/check_health.json`
- `docs/proof/receipts-m19b-success-true-20260227T033503Z/notify.json`

## Conclusion

The targeted `YAML_FILE_ERROR` is fixed and no longer blocks bringup.  
DR bringup now advances past buildspec parsing and fails later on an unrelated IAM permission gap.
