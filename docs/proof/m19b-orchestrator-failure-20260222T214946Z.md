# M19B Orchestrator Failure-Path Receipt Bundle (2026-02-22)

Intentional, deterministic failure in check_health phase. No infra created; no teardown required.

## Failure Injected

**Mode:** Option C — simulate check_health failing via invalid input

**Input:** `max_freshness_hours="not-a-number"` (string instead of numeric)

**Expected:** Lambda `float()` raises `ValueError` when parsing `max_freshness_hours`; check_health fails before health logic runs; HandlePhaseFailure → notify → FailWorkflow.

## Observed

| Step | Expected | Observed |
|------|----------|----------|
| check_health | ValueError / Lambda failure | ✅ `could not convert string to float: 'not-a-number'` |
| Catch | Route to HandlePhaseFailure | ✅ |
| notify | SNS published with failure details | ✅ `dr_orchestrator_phase_failed`, phase_name=check_health |
| FailWorkflow | Execution ends FAILED | ✅ |
| bringup | Not reached | ✅ (no CodeBuild, no EC2) |
| Teardown | N/A (no infra) | ✅ No runners created |

## Execution ARN

```
arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-failure-20260222T214946Z
```

**Status:** FAILED  
**Started:** 2026-02-22T21:49:51Z  
**Stopped:** 2026-02-22T21:49:55Z (~4s)

## Receipt URIs (S3)

| Phase | URI |
|-------|-----|
| check_health | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-failure-20260222T214946Z/check_health.json` |
| notify | `s3://jobintel-prod1/jobintel/dr-orchestrator/receipts/m19b-failure-20260222T214946Z/notify.json` |

## Failure Classification

- **Phase:** check_health
- **Error type:** RuntimeError (wrapping ValueError from `float()`)
- **Root cause:** Invalid `max_freshness_hours` input (non-numeric string)
- **Receipt status:** check_health receipt written with `status: "error"`; notify receipt written with `status: "ok"`

## Teardown Confirmation

- **DR runners:** None (bringup never ran)
- **EC2 instances (Purpose=jobintel-dr):** 0 running/pending
- **Teardown required:** No

## Local Artifacts (docs/proof)

- `m19b-orchestrator-failure-execution-history-20260222T214946Z.json` — Step Functions execution history export
- `m19b-orchestrator-failure-check_health-20260222T214946Z.json` — check_health receipt copy
- `m19b-orchestrator-failure-notify-20260222T214946Z.json` — notify receipt copy

## Cost Notes

- Lambda: 2 invocations (check_health, notify)
- SNS: 1 publish
- S3: 2 put_object (receipts)
- No CodeBuild, no EC2, no Step Functions sync wait
