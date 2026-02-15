# Milestone 12 Proof: Provider Availability Artifact v1

Date: 2026-02-15

## What changed

- Added versioned schema: `schemas/provider_availability.schema.v1.json`
- Implemented per-run provider availability artifact emission in pipeline runner:
  - path: `state/runs/<run_id>/artifacts/provider_availability_v1.json`
  - written from canonical finalize path (success and controlled failure)
- Artifact pointer is recorded in run metadata (`run_report.json`) as:
  - `provider_availability_artifact`
- Added run summary exposure:
  - included in `primary_artifacts` as `artifact_key=provider_availability`
  - quicklink surfaced as `quicklinks.provider_availability`

## Artifact v1 contents

For each provider, artifact includes:
- `provider_id`
- `mode` (`snapshot` / `live` / `disabled`)
- flags: `enabled`, `snapshot_enabled`, `live_enabled`
- `availability` (`available` / `unavailable`)
- explicit `reason_code`
- policy details:
  - robots policy fields
  - network shield decision fields
  - canonical URL policy snapshot fields

Top-level includes:
- `generated_at_utc`
- `provider_registry_sha256` (when registry load is available)

## Tests added/updated

- `tests/test_run_health_artifact.py`
  - validates provider availability artifact schema
  - asserts artifact exists on success
  - asserts artifact exists on controlled failure path
  - asserts run report pointer to artifact exists
- `tests/test_run_summary_artifact.py`
  - asserts run summary includes provider availability in primary artifacts

## Verification commands

- Focused:
  - `pytest -q tests/test_run_health_artifact.py tests/test_run_summary_artifact.py tests/test_jobintel_cli.py tests/test_smoke_metadata.py`
- Full:
  - `make format`
  - `make lint`
  - `make ci-fast`
  - `make gate`

## Sample snippet

```json
{
  "provider_availability_schema_version": 1,
  "provider_registry_sha256": "<sha256-or-null>",
  "providers": [
    {
      "provider_id": "openai",
      "mode": "snapshot",
      "availability": "available",
      "reason_code": "ok"
    }
  ]
}
```
