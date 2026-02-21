# M17 Artifact Contract + UI Safety Consolidation (2026-02-21)

## Scope
Tighten contract consistency across:
- `src/ji_engine/artifacts/catalog.py`
- `src/ji_engine/dashboard/app.py`
- `tests/test_artifact_contract_registry.py`
- `scripts/dashboard_offline_sanity.py`
- `tests/test_dashboard_offline_sanity.py`

No artifact filename/path contracts were changed.

## Invariants Enforced
1. Single-source canonical UI-safe artifact registry exists in `catalog.py`:
   - `ui_safe_catalog_exact_keys()`
   - `ui_safe_catalog_patterns()`
   - `canonical_ui_safe_artifact_keys()`
   - `UI_SAFE_PATTERN_REPRESENTATIVE_KEYS`
   - `UI_SAFE_SCHEMA_SPECS`
   - `UI_SAFE_NONSCHEMA_CANONICAL_KEYS`
2. Dashboard schema version exposure is sourced from one registry:
   - `DASHBOARD_SCHEMA_VERSION_BY_ARTIFACT_KEY`
   - `src/ji_engine/dashboard/app.py::_schema_version_for_artifact_key`
3. Offline sanity fixtures now cover the full canonical UI-safe set (including pattern representatives and error artifact).
4. Registry tests enforce cross-surface parity between catalog registry, dashboard mapping, artifact path helpers, and offline sanity fixtures.
5. Catalog schema-validation registry now includes `provider_availability_v1.json` (same fail-closed model used by other schema-bound artifacts).

## Determinism Notes
- All registry enumerations and checks are sorted.
- Offline sanity iterates canonical artifacts in deterministic order.
- No network dependency added.

## Validation Commands
```bash
PATH=.venv/bin:$PATH make format
PATH=.venv/bin:$PATH make lint
PATH=.venv/bin:$PATH make ci-fast
PATH=.venv/bin:$PATH make gate
```

## Validation Results
- `make lint`: pass
- `make ci-fast`: pass (`720 passed, 17 skipped`)
- `make gate`: pass
  - snapshot immutability: pass
  - replay smoke: pass (`mismatched=0`, `missing=0`)
