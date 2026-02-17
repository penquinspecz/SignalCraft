# Milestone 12 Proof: Deterministic Forced Failure Receipts (2026-02-15)

## Change Receipt

Deterministic forced-failure harness added for dev/test:

- **Trigger**: `JOBINTEL_FORCE_FAIL_STAGE=<stage_name>` (env var)
- **Behavior**: At the start of `record_stage`, if the env var matches the current stage name, the pipeline raises `SystemExit` with a deterministic message before the stage runs.
- **Failure path**: Same as normal stage failure: exception propagates to handler, which calls `_finalize("error", {"error": ..., "failed_stage": ...})`, ensuring run_health, run_summary, and other receipts are emitted.

Determinism contract:

- No nondeterministic fields added; `FORCED_FAILURE` is a fixed failure code.
- Pipeline ordering unchanged; forced failure occurs at stage boundary.
- Replay and snapshot baseline unchanged.

## How to Trigger Forced Failure

```bash
# Force failure at scrape (before scrape runs)
JOBINTEL_FORCE_FAIL_STAGE=scrape python scripts/run_daily.py --no_subprocess --profiles cs --no_post

# Force failure at classify (after scrape succeeds)
JOBINTEL_FORCE_FAIL_STAGE=classify python scripts/run_daily.py --no_subprocess --profiles cs --no_post

# For openai-only runs, stage names are: scrape, classify, enrich, ai_augment, score:cs, etc.
# For multi-provider: scrape:openai, classify:openai, enrich:openai, score:openai:cs, etc.
```

## Where Artifacts Appear

On forced failure, the pipeline still runs `_finalize`, which writes:

| Artifact | Location | Schema |
|----------|----------|--------|
| run_health | `state/runs/<run_id>/run_health.v1.json` | run_health.schema.v1.json |
| run_summary | `state/runs/<run_id>/run_summary.v1.json` | run_summary.schema.v1.json |
| run_report | `state/runs/<run_id>/run_report.json` | (legacy) |

Receipts:

- `run_health.status` = `"failed"`
- `run_health.failed_stage` = stage name that was forced
- `run_health.failure_codes` includes `"FORCED_FAILURE"`
- `run_summary` points to run_health and reflects the failure status

## Provider Availability

- **Current behavior**: `provider_availability` is built from `provenance_by_provider` in `_finalize` and **logged** (not written as a separate artifact file).
- **On early failure** (e.g. scrape, classify): provenance may be empty; provider_availability will show `"unknown"` for providers.
- **Fail-closed rule**: The runner does not emit a standalone `provider_availability` artifact file. It is included in run_health/run_summary where applicable. Tests document this behavior.

## Evidence Paths

- `src/ji_engine/pipeline/runner.py`: `record_stage` checks `JOBINTEL_FORCE_FAIL_STAGE`; `_failure_code_for_context` maps forced-failure error text to `FORCED_FAILURE`
- `schemas/run_health.schema.v1.json`: `FORCED_FAILURE` added to failure_codes enum
- `tests/test_run_health_artifact.py`: `test_run_health_written_on_forced_failure`, `test_provider_availability_on_forced_failure`

## Commands Run

```bash
make format
make lint
make ci-fast
make gate
```
