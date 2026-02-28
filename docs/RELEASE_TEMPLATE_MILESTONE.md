# SignalCraft Milestone Release Template

Use this for `mNN-YYYYMMDDTHHMMSSZ` releases.

## Milestone Context
- milestone: `MNN`
- intent: <what this milestone proves>

## What was exercised
- success/failure path exercised: <explicit value>
- boundaries: <what was intentionally not executed>

## Execution Evidence
- execution_arn: `arn:aws:states:...`
- terminal_state: `<state name>`
- terminal_status: `SUCCEEDED|FAILED|ABORTED`
- receipts_root: `docs/proof/receipts-<run-name>/`

## Images (Digest-pinned)
- IMAGE_REF: `<account>.dkr.ecr.<region>.amazonaws.com/<repo>@sha256:<64-hex>`
- Digest: `sha256:<64-hex>`
- Architectures: `amd64, arm64`

## Guardrails/Determinism checks
- `./scripts/audit_determinism.sh`: `PASS|FAIL`
- `python3 scripts/ops/check_dr_docs.py`: `PASS|FAIL`
- `python3 scripts/ops/check_dr_guardrails.py`: `PASS|FAIL`

## Outcome + Next steps
- outcome: <explicit result>
- next_step: <explicit next blocker or "None">

## Proof References (repo paths)
- `docs/proof/<execution-history>.json`
- `docs/proof/<describe>.json`
- `docs/proof/<proof-doc>.md`
