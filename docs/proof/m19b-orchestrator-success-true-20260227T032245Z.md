# M19B Orchestrator — Success-Path Rehearsal (`force_run=true`) 2026-02-27

## Summary

- **Execution ARN:** `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T032245Z`
- **Main SHA:** `8d76c3313cc6666c008ddbd7c736d06f5fa02bfe`
- **Outcome:** **NOT PROVEN** (failed in `bringup`; chain did not reach `restore -> validate -> request_manual_approval`)
- **Previous blocker check:** This run did **not** fail with `CodeBuild.AccountLimitExceededException`; CodeBuild started and reached `DOWNLOAD_SOURCE`.

## Trigger Details

- **Execution name:** `m19b-success-true-20260227T032245Z`
- **Region:** `us-east-1`
- **Force run:** `true`

## Main Branch Gate Check (pre-run)

- Remote `main` SHA matched local HEAD: `8d76c3313cc6666c008ddbd7c736d06f5fa02bfe`
- Check-runs on that SHA were **not fully green** at trigger time (`refresh` and `build-and-gate` showed `failure`; other listed checks were `success`/`skipped`).

## Failure Classification

- **Failing phase:** `bringup` (`BringupInfra`)
- **Step Functions terminal error:** `DRPhaseFailed`
- **CodeBuild status:** `FAILED`
- **Failed CodeBuild phase:** `DOWNLOAD_SOURCE`
- **Status code:** `YAML_FILE_ERROR`
- **Message:** `did not find expected key at line 15`
- **Build ARN:** `arn:aws:codebuild:us-east-1:048622080012:build/signalcraft-dr-orchestrator-dr-infra:28fb7bd0-c651-4865-babe-388c4c7da8d1`

## IMAGE_REF (digest context)

- Backup metadata for `s3://jobintel-prod1/jobintel/backups/backup-20260221T061624Z` does not include image digest fields.
- Digest reference used for M19 DR context (latest recorded in-repo):  
  `048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:b33a382bca2456df8a4f8a0343f10c63503dbbbb44f45bf1be5a0684ef2e05b7`

## Receipt Paths

| Phase | Status | Repo-local copy | S3 URI |
|---|---|---|---|
| `check_health` | present | `docs/proof/receipts-m19b-success-true-20260227T032245Z/check_health.json` | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260227T032245Z/check_health.json` |
| `bringup` | missing receipt | — | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260227T032245Z/bringup.json` |
| `restore` | not reached | — | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260227T032245Z/restore.json` |
| `validate` | not reached | — | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260227T032245Z/validate.json` |
| `notify` | present (failure notify) | `docs/proof/receipts-m19b-success-true-20260227T032245Z/notify.json` | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260227T032245Z/notify.json` |
| `request_manual_approval` | not reached | — | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260227T032245Z/request_manual_approval.json` |
| `record_manual_decision` | not reached | — | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-success-true-20260227T032245Z/record_manual_decision.json` |

## Exported Artifacts (repo)

- `docs/proof/m19b-orchestrator-success-true-describe-20260227T032245Z.json`
- `docs/proof/m19b-orchestrator-success-true-execution-history-20260227T032245Z.json`
- `docs/proof/receipts-m19b-success-true-20260227T032245Z/check_health.json`
- `docs/proof/receipts-m19b-success-true-20260227T032245Z/notify.json`
- `docs/proof/receipts-m19b-success-true-20260227T032245Z/backup-metadata.json`

## Conclusion

M19B full success-path rehearsal remains **unproven** as of `2026-02-27T03:22:45Z` because the run failed in `bringup` before `restore`, `validate`, and manual approval states.
