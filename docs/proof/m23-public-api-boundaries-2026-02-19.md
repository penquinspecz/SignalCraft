# M23 Public API Boundaries Guardrail (2026-02-19)

## Scope
Define and enforce a minimal public API boundary contract to prevent new coupling to pipeline internals.

## Boundaries Enforced

Public entrypoints documented:
- `scripts/run_daily.py`
- `src/jobintel/cli.py`
- `src/ji_engine/dashboard/app.py`
- `src/ji_engine/run_repository.py`

Internal modules called out as non-public:
- `src/ji_engine/pipeline/runner.py`
- `src/ji_engine/pipeline/*`

Import-boundary enforcement:
- `src/jobintel/**` must not import `ji_engine.pipeline` or `ji_engine.pipeline.*`
- `src/ji_engine/dashboard/**` must not import `ji_engine.pipeline` or `ji_engine.pipeline.*`

## Added Artifacts

- Contract doc: `docs/PUBLIC_API_BOUNDARIES.md`
- Enforcement test: `tests/test_public_api_boundaries.py`
  - test name: `test_public_api_layers_do_not_import_pipeline_internals`

## Determinism/Behavior Impact

- No runtime code paths changed.
- No schema/path/output contract changed.
- This is a static import guard test plus documentation.

## Sample Failure Output

If a forbidden import is introduced, the test fails with a deterministic path+line report, for example:

```text
E   AssertionError: src/jobintel/cli.py:42 imports forbidden module 'ji_engine.pipeline.runner'
```

## Validation Commands

```bash
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make lint
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make ci-fast
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make gate
```
