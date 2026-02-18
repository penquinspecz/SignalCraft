# M20 Dual-Run Deterministic Diff Proof - 2026-02-17

## Dual-Run Contract (AWS vs On-Prem)

The deterministic comparison contract enforced by `scripts/compare_run_artifacts.py` is:

1. Same input snapshot set:
   - `run_summary.v1.json.snapshot_manifest.applicable`
   - `run_summary.v1.json.snapshot_manifest.sha256`
2. Same scoring configuration:
   - `run_summary.v1.json.scoring_config.source`
   - `run_summary.v1.json.scoring_config.config_sha256`
   - `run_summary.v1.json.scoring_config.provider`
   - `run_summary.v1.json.scoring_config.profile`
3. Same provider registry:
   - `artifacts/provider_availability_v1.json.provider_registry_sha256`
4. Same candidate namespace:
   - `candidate_id` must match across both runs.
5. Same run identity:
   - default: `run_id` must match exactly.
   - deterministic equivalent mode: pass `--allow-run-id-drift`.

## Compared Artifacts

- `run_summary.v1.json` (timestamps/env metadata ignored)
- `run_health.v1.json` (timestamps/env metadata ignored)
- `artifacts/provider_availability_v1.json` (timestamps/env metadata ignored)
- Ranked outputs from `run_summary.ranked_outputs`:
  - `ranked_json`
  - `ranked_csv`
  - `ranked_families_json`

## Failure Rules

The comparator exits non-zero when:

- ranked job order differs
- ranked score values differ
- artifact schema version differs (`*_schema_version`)
- schema validation fails for run summary/run health/provider availability
- contract fields differ (snapshot/scoring/provider registry/candidate namespace/run id policy)

## Commands

```bash
make lint
make ci-fast
make gate
```

## Validation Results

- `make lint`: pass
- `make ci-fast`: pass (`671 passed, 16 skipped`)
- `make gate`: pass (`671 passed, 16 skipped`)
- Snapshot immutability check: pass
- Replay smoke check: pass (`checked=6 matched=6 mismatched=0 missing=0`)

## Comparator Regression Coverage

`tests/test_compare_run_artifacts.py` validates:

- pass when only timestamps/environment metadata differ
- fail when ranked job order differs
- fail when ranked score values differ
- fail when artifact schema version differs

## Expected Comparator Usage

```bash
.venv/bin/python scripts/compare_run_artifacts.py \
  /path/to/aws/run_dir \
  /path/to/onprem/run_dir \
  --repo-root /Users/chris.menendez/Projects/signalcraft
```

Deterministic-equivalent run IDs:

```bash
.venv/bin/python scripts/compare_run_artifacts.py \
  /path/to/aws/run_dir \
  /path/to/onprem/run_dir \
  --allow-run-id-drift \
  --repo-root /Users/chris.menendez/Projects/signalcraft
```
