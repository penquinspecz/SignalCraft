# Providers

Provider expansion must stay deterministic and offline-reproducible.

## Add A Provider In 10 Minutes

1. Scaffold snapshot fixture directory first (no network in tests):

```bash
make provider-scaffold provider=<provider_id>
```

2. Generate a schema-valid template entry:

```bash
make provider-template provider=<provider_id>
```

3. Add the rendered entry to `config/providers.json` with these defaults:
- `mode: "snapshot"` first
- `live_enabled: false` first
- `allowed_domains` explicitly set
- `snapshot_path` and `snapshot_dir` under `data/<provider_id>_snapshots`

4. Replace placeholder snapshot with captured fixture before enabling live mode:

```bash
PYTHONPATH=src .venv/bin/python scripts/update_snapshots.py \
  --provider <provider_id> \
  --out_dir data/<provider_id>_snapshots \
  --apply
```

5. Update pinned snapshot manifest for all enabled snapshot providers:

```bash
PYTHONPATH=src .venv/bin/python scripts/verify_snapshots_immutable.py
```

If the script reports missing manifest entries for your provider, add the provider fixture hash/bytes to
`tests/fixtures/golden/snapshot_bytes.manifest.json`.

6. Run deterministic local gates:

```bash
make lint
make gate
```

## Guardrails

- Tests must remain no-network.
- Snapshot fixtures are required for enabled snapshot providers.
- Snapshot bytes must be pinned in `tests/fixtures/golden/snapshot_bytes.manifest.json`.
- `make gate` enforces:
  - unit tests
  - snapshot immutability
  - replay smoke determinism
