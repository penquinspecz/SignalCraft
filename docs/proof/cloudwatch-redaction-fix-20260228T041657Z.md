# CloudWatch pagination token redaction fix

## Why
Some DR proof artifacts include raw CloudWatch `get-log-events` output. Those JSON payloads contain pagination tokens (`nextForwardToken`, `nextBackwardToken`, and similar `next*Token` keys) that can trigger secret scanning.
These tokens are not authentication credentials, but they are high-entropy opaque values and are redacted to avoid scanner noise and accidental propagation in committed artifacts.

## What changed
- Added deterministic redaction helper:
  - `scripts/ops/redact_cloudwatch_tokens.py`
- Added canonical sanitized export command for CodeBuild CloudWatch logs:
  - `scripts/ops/export_codebuild_cloudwatch_log_events.sh`
- Added deterministic smoke/regression check:
  - `scripts/ops/test_redact_cloudwatch_tokens.sh`
- Updated runbook/docs to route proof capture through sanitized path:
  - `docs/dr_orchestrator.md`
  - `docs/OPERATIONS.md`

## Where redaction happens
`export_codebuild_cloudwatch_log_events.sh` writes raw AWS output to a temp file, then calls:

`python3 scripts/ops/redact_cloudwatch_tokens.py --input <raw> --output <final>`

Redaction rule:
- Any JSON key matching `^next.*token$` (case-insensitive) has its value replaced with `<REDACTED>`.
- Keys are preserved; only values are replaced.
- The transform is idempotent.

## Example (small)
Before:
```json
{
  "nextForwardToken": "f/abc123/s",
  "nextBackwardToken": "b/def456/s",
  "nested": {"nextToken": "ghi789", "keep": "value"}
}
```

After:
```json
{
  "nextForwardToken": "<REDACTED>",
  "nextBackwardToken": "<REDACTED>",
  "nested": {"nextToken": "<REDACTED>", "keep": "value"}
}
```

## Commands run
- Discovery:
  - `rg -n "get-log-events|nextForwardToken|nextBackwardToken|codebuild-cloudwatch-log-events" scripts docs`
  - `rg -n "get-execution-history|describe-execution|codebuild|CloudWatch" docs/dr_orchestrator.md docs/OPERATIONS.md scripts/ops/dr_status.sh scripts/ops/dr_approve.sh`
- Validation:
  - `python3 -m py_compile scripts/ops/redact_cloudwatch_tokens.py`
  - `scripts/ops/test_redact_cloudwatch_tokens.sh`
  - `~/.local/bin/ruff check scripts/ops/redact_cloudwatch_tokens.py`
  - `./scripts/audit_determinism.sh`
  - `python3 scripts/ops/check_dr_docs.py`
  - `python3 scripts/ops/check_dr_guardrails.py`
