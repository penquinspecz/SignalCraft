# Milestone 10 Proof: Provider Tombstone v1

Date: 2026-02-15

## What changed

- Added `tombstone` support to provider schema in `schemas/providers.schema.v1.json`:
  - `enabled: bool`
  - `reason: string`
  - `date: string` (optional)
- Enforced tombstone policy in provider registry normalization/selection:
  - tombstoned providers are forced `enabled=false` and `live_enabled=false`
  - explicit selection of tombstoned providers fails closed with reason
  - `--providers all` excludes tombstoned providers
- Added provenance visibility for explainability:
  - run report `provenance.build.provider_tombstones`
  - run report `selection.provider_tombstones` (when any exist)
- Extended authoring helper `scripts/provider_authoring.py`:
  - `tombstone` command to set/clear tombstone deterministically
  - enabling a tombstoned provider is explicitly blocked

## Determinism and safety

- Deterministic provider ordering remains provider-id sorted.
- Tombstone maps in provenance are provider-id sorted.
- No snapshot fixture baselines were modified.

## Verification commands

- Focused:
  - `pytest -q tests/test_provider_registry.py tests/test_provider_authoring.py tests/test_run_metadata.py`
- Full:
  - `make format`
  - `make lint`
  - `make ci-fast`
  - `make gate`

## Sample provenance snippet

```json
{
  "provenance": {
    "build": {
      "provider_tombstones": {
        "legacy": {
          "reason": "tombstoned_by_policy",
          "date": "2026-02-15"
        }
      }
    }
  }
}
```
