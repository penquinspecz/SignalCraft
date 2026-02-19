## Public API Boundaries

This document defines the supported public entrypoints for SignalCraft/JIE and the internal modules that are not part of the public contract.

### Supported Entrypoints

These are the supported integration surfaces:

- `scripts/run_daily.py`
- `src/jobintel/cli.py`
- `src/ji_engine/dashboard/app.py` (dashboard/API surface)
- `src/ji_engine/run_repository.py` (run read seam)

### Internal Modules

Everything else should be treated as internal implementation detail unless explicitly documented otherwise.

In particular:

- `src/ji_engine/pipeline/runner.py`
- `src/ji_engine/pipeline/*`

These are orchestration internals and are not public extension points.

### What Not To Import

To prevent cross-layer coupling and entropy:

- `src/jobintel/**` must not import `ji_engine.pipeline` modules.
- `src/ji_engine/dashboard/**` must not import `ji_engine.pipeline` modules.

Use stable seams instead:

- Run access via `RunRepository` (`src/ji_engine/run_repository.py`)
- Artifact validation/catalog via `src/ji_engine/artifacts/catalog.py`
- CLI-to-run invocation via `scripts/run_daily.py`

### How To Extend Safely

When adding functionality:

1. Extend an existing public seam first (CLI args, dashboard endpoint, repository read API).
2. Keep pipeline internals behind those seams.
3. Add tests that enforce boundary expectations (import-boundary checks and contract tests).
4. Add a proof receipt in `docs/proof/` for any new cross-module contract.
