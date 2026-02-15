# Milestone 10 Proof: Provider Registry Hash in Provenance

Date: 2026-02-15

## What changed

- Added deterministic provider registry provenance helper: `provider_registry_provenance()` in `src/ji_engine/providers/registry.py`.
- Registry hash is now written into run-report build provenance in `src/ji_engine/pipeline/runner.py` as:
  - `provider_registry_schema_version`
  - `provider_registry_sha256`
- Hashing is canonical and deterministic:
  - normalized registry entries from `load_providers_config()`
  - canonical JSON serialization (`sort_keys=True`, compact separators)
  - SHA-256 hex digest

## Determinism and safety notes

- Hash value is stable for identical registry content.
- Hash value changes when registry content changes.
- No snapshot fixture files were modified.

## Verification

- Focused tests:
  - `pytest -q tests/test_provider_registry.py tests/test_run_metadata.py tests/test_run_summary_artifact.py`
- Full gate commands (run in PR validation):
  - `make format`
  - `make lint`
  - `make ci-fast`
  - `make gate`

## Sample provenance snippet

```json
{
  "provenance": {
    "build": {
      "provider_registry_schema_version": 1,
      "provider_registry_sha256": "<64-char sha256 hex>"
    }
  }
}
```
