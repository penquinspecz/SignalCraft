# CI Smoke Gate Contract

This document is the operational contract for CI smoke gates.
It describes exactly what CI runs, what each step proves, and how to debug failures quickly.

Product naming note:
- SignalCraft is the product name.
- JIE (Job Intelligence Engine) remains the internal engine codename in code paths and env vars.

## CI Step Order

1. `actions/checkout@v4`
2. `actions/setup-python@v5` (`python-version: 3.12.12`, pip cache keyed by `requirements.txt`)
3. **Install deps**
   - `python -m venv .venv`
   - `.venv/bin/python -m pip install --upgrade pip==25.0.1 setuptools wheel pip-tools==7.4.1`
   - `.venv/bin/python -m pip install -r requirements.txt`
   - `.venv/bin/python -m pip install -e .`
   - `.venv/bin/python -m pip install -e ".[dev]"`
4. **Gate**
   - `make gate-ci`
5. **Determinism contract checks**
   - inline fixture writes `/tmp/jobintel_ci_state/runs/ci-run/run_report.json`
   - `.venv/bin/python scripts/publish_s3.py --run-dir /tmp/jobintel_ci_state/runs/ci-run --plan --json`
   - `.venv/bin/python scripts/replay_run.py --run-dir /tmp/jobintel_ci_state/runs/ci-run --profile cs --strict --json`
6. **CronJob smoke (offline)**
   - `make cronjob-smoke`
7. **Roadmap discipline guard (warn-only)**
   - `.venv/bin/python scripts/check_roadmap_discipline.py`
   - `continue-on-error: true`

Sources:
- `.github/workflows/ci.yml` (unit + determinism + cronjob smoke)
- `.github/workflows/docker-smoke.yml` (containerized smoke gate)

## Gate Contracts

### 1) `make gate-ci` contract

`make gate-ci` expands to `gate-truth` -> `gate-fast`:

- `pytest -q`
  - proves unit/integration suite passes in CI image/runtime.
- `python scripts/verify_snapshots_immutable.py`
  - proves snapshot bytes match pinned manifest.
- `python scripts/replay_smoke_fixture.py`
  - proves replay path can validate deterministic run artifacts.
- `docker build --no-cache --build-arg RUN_TESTS=1 -t jobintel:tests .`
  - proves Docker build contract and in-image test path.

Source: `Makefile` targets `gate-fast`, `gate-truth`, `gate-ci`.

### 2) Determinism contract checks

- Creates a minimal run fixture at `/tmp/jobintel_ci_state/runs/ci-run`.
- Writes `run_report.json` with verifiable artifact hash fields.
- `publish_s3.py --plan --json` proves publish contract planning from run artifacts without cloud writes.
- `replay_run.py --strict --json` proves strict replay/verifiability path succeeds on the fixture.

Expected evidence:
- `/tmp/jobintel_ci_state/runs/ci-run/run_report.json`
- stdout JSON from `publish_s3.py` plan
- stdout JSON from `replay_run.py --strict`

Source: inline script + commands in `.github/workflows/ci.yml`.

### 3) `make cronjob-smoke` contract

- Runs `scripts/cronjob_simulate.py` with temp `JOBINTEL_DATA_DIR` and `JOBINTEL_STATE_DIR`.
- Forces deterministic run id: `JOBINTEL_CRONJOB_RUN_ID=2026-01-01T00:00:00Z`.
- Uses snapshot-only/offline settings:
  - `CAREERS_MODE=SNAPSHOT`
  - `EMBED_PROVIDER=stub`
  - `ENRICH_MAX_WORKERS=1`
  - `DISCORD_WEBHOOK_URL=`
- Replays produced run strictly:
  - `scripts/replay_run.py --run-dir <tmp>/runs/20260101T000000Z --profile cs --strict --json`

Expected evidence:
- run dir under temp state path containing run artifacts + `run_report.json`
- replay strict exits `0`.

Source: `Makefile` target `cronjob-smoke`.

### 4) Required artifact checklist (docker smoke)

Validate artifact layout offline:

```bash
.venv/bin/python scripts/ci_artifact_contract_check.py smoke_artifacts
```

Required files:

- `smoke_artifacts/exit_code.txt`
- `smoke_artifacts/metadata.json`
- `smoke_artifacts/run_report.json`
- `smoke_artifacts/smoke.log`
- `smoke_artifacts/smoke_summary.json`
- `smoke_artifacts/openai_labeled_jobs.json`
- `smoke_artifacts/openai_ranked_jobs.cs.json`
- `smoke_artifacts/openai_ranked_jobs.cs.csv`

### 5) Roadmap guard (warn-only) contract

- Runs `scripts/check_roadmap_discipline.py`.
- Findings are logged but do not fail CI yet (`continue-on-error: true`).

Source: `.github/workflows/ci.yml`.

### 5) Docker smoke gate (containerized)

Workflow: `.github/workflows/docker-smoke.yml`

Exact invocation (env vars + command):

```bash
export CONTAINER_NAME=jobintel_smoke
export SMOKE_ARTIFACTS_DIR="$GITHUB_WORKSPACE/smoke_artifacts"
export SMOKE_PROVIDERS=openai
export SMOKE_PROFILES=cs
export SMOKE_SKIP_BUILD=1
export SMOKE_UPDATE_SNAPSHOTS=0
export SMOKE_MIN_SCORE=40
./scripts/smoke_docker.sh --skip-build --providers openai --profiles cs
```

Required artifacts (in `smoke_artifacts/`):
- `exit_code.txt` (container exit code)
- `smoke.log` (combined stdout/stderr)
- `docker_context.txt` (context + docker info)
- `run_report.json` (real or placeholder on failure)
- `smoke_summary.json` (status + missing_artifacts + tail)
- `metadata.json` (smoke metadata)
- `openai_labeled_jobs.json`
- `openai_ranked_jobs.cs.json`
- `openai_ranked_jobs.cs.csv`
- `openai_shortlist.cs.md` (may be empty, must exist)
- `openai_top.cs.md` (may be empty, must exist)

## Failure Modes And What To Inspect

Before drilling into a failure, reproduce with an AWS-isolated env so local credentials or metadata do not alter behavior:

```bash
export AWS_CONFIG_FILE=/dev/null
export AWS_SHARED_CREDENTIALS_FILE=/dev/null
export AWS_EC2_METADATA_DISABLED=true
export PYTHONPATH=src
```

### Failure: `make gate-ci` in `pytest -q`

Inspect:

```bash
.venv/bin/python -m pytest -q -x
.venv/bin/python -m pytest -q <failing_test_path>::<test_name> -vv
```

### Failure: provider config contract (schema fail-closed)

Symptoms: provider load fails with missing required keys/unknown keys/type mismatch.

Inspect:

```bash
export PYTHONPATH=src
./.venv/bin/python -m pytest -q tests/test_provider_registry.py -vv
./.venv/bin/python -m pytest -q tests/test_run_scrape_provider_selection.py -vv
./.venv/bin/python -m pytest -q tests/test_run_daily_provider_selection.py -vv
```

Then inspect:
- `config/providers.json`
- `schemas/providers.schema.v1.json`
- `src/ji_engine/providers/registry.py`

### Failure: snapshot immutability check

Symptoms: `scripts/verify_snapshots_immutable.py` reports hash/bytes mismatch.

Inspect:

```bash
.venv/bin/python scripts/verify_snapshots_immutable.py
git status --short data/openai_snapshots
```

### Failure: replay smoke fixture

Symptoms: `scripts/replay_smoke_fixture.py` non-zero.

Inspect:

```bash
.venv/bin/python scripts/replay_smoke_fixture.py
.venv/bin/python scripts/replay_run.py --help
```

### Failure: Docker truth gate build

Symptoms: `docker build --no-cache --build-arg RUN_TESTS=1` fails.

Inspect:

```bash
DOCKER_BUILDKIT=1 docker build --no-cache --progress=plain --build-arg RUN_TESTS=1 -t jobintel:tests .
```

### Failure: optional dashboard dependency path

Symptoms: dashboard import/runtime error (for example missing `fastapi`/`uvicorn`).
Core CI smoke should not fail for dashboard extras alone.

Inspect:

```bash
./.venv/bin/python - <<'PY'
import importlib.util
missing = [name for name in ("fastapi", "uvicorn") if importlib.util.find_spec(name) is None]
print({"missing_dashboard_deps": missing})
PY
./.venv/bin/python -m pytest -q tests/test_dashboard_app.py -vv
```

### Failure: determinism contract checks

Symptoms: `publish_s3.py --plan --json` or `replay_run.py --strict` fails.

Inspect:

```bash
export JOBINTEL_DATA_DIR=/tmp/jobintel_ci_data
export JOBINTEL_STATE_DIR=/tmp/jobintel_ci_state
ls -R /tmp/jobintel_ci_state/runs/ci-run
cat /tmp/jobintel_ci_state/runs/ci-run/run_report.json
.venv/bin/python scripts/publish_s3.py --run-dir /tmp/jobintel_ci_state/runs/ci-run --plan --json
.venv/bin/python scripts/replay_run.py --run-dir /tmp/jobintel_ci_state/runs/ci-run --profile cs --strict --json
```

### Failure: `make cronjob-smoke`

Inspect:

```bash
make cronjob-smoke
tmp_data=$(mktemp -d); tmp_state=$(mktemp -d)
JOBINTEL_DATA_DIR=$tmp_data JOBINTEL_STATE_DIR=$tmp_state JOBINTEL_CRONJOB_RUN_ID=2026-01-01T00:00:00Z CAREERS_MODE=SNAPSHOT EMBED_PROVIDER=stub ENRICH_MAX_WORKERS=1 DISCORD_WEBHOOK_URL= .venv/bin/python scripts/cronjob_simulate.py
ls -R "$tmp_state"
```

### Failure: Docker smoke gate

Inspect:

```bash
ls -la smoke_artifacts
cat smoke_artifacts/exit_code.txt
tail -n 200 smoke_artifacts/smoke.log
cat smoke_artifacts/docker_context.txt
```

Common causes:
- missing image tag when `SMOKE_SKIP_BUILD=1`
- snapshot validation failed inside container
- missing artifacts copied from container (see `smoke_summary.json`)

### Failure: `deps-check` / stale lock contract

Inspect:

```bash
make deps-check
make deps-sync
git diff -- requirements.txt requirements-dev.txt
```

If local network is unavailable, local export may use deterministic installed-env fallback.
CI remains strict and fail-closed.

### Failure: redaction enforcement (if enabled)

Symptoms: run aborts with secret-like tokens found in generated artifacts.

Inspect:

```bash
REDACTION_ENFORCE=1 ./.venv/bin/python scripts/run_daily.py --offline --snapshot-only --providers openai --profiles cs
./.venv/bin/python -m pytest -q tests/test_redaction_scan.py -vv
```

If failing on generated outputs, inspect:
- `state/runs/<run_id>/run_report.json`
- `state/runs/<run_id>/*` JSON/markdown artifact files flagged in the error

## Where To Look First (Decision Tree)

1. Did `pytest -q` fail in CI?
   - Run `./.venv/bin/python -m pytest -q -x` and inspect the first failing test.
2. Did snapshot validation fail (`verify_snapshots_immutable.py`)?
   - Inspect `data/*_snapshots` and rerun `./.venv/bin/python scripts/verify_snapshots_immutable.py`.
3. Did provider load/selection fail before scraping?
   - Inspect `config/providers.json`, schema file, and registry tests listed above.
4. Did smoke artifacts fail contract checks?
   - Inspect `smoke_artifacts/smoke_summary.json` then `smoke_artifacts/smoke.log`.
5. Did replay/publish determinism checks fail?
   - Start at `/tmp/jobintel_ci_state/runs/ci-run/run_report.json`, then rerun `publish_s3.py --plan --json` and `replay_run.py --strict --json`.
6. Did cronjob smoke fail?
   - Run `make cronjob-smoke`, inspect temp state run dir and its `run_report.json`.
7. Did redaction enforcement fail (when enabled)?
   - Run redaction tests and inspect flagged artifact paths in the exception message.

## Reproduce CI Smoke Locally

### Local Python path (fastest)

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip==25.0.1 setuptools wheel pip-tools==7.4.1
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install -e ".[dev]"

make gate-ci
make cronjob-smoke
.venv/bin/python scripts/check_roadmap_discipline.py
```

AWS-isolated equivalent:

```bash
AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true PYTHONPATH=src make gate-ci
AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true PYTHONPATH=src make cronjob-smoke
AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true PYTHONPATH=src ./.venv/bin/python -m pytest -q
```

### Docker truth build path

```bash
DOCKER_BUILDKIT=1 docker build --no-cache --build-arg RUN_TESTS=1 -t jobintel:tests .
```

## Determinism Rules (CI Smoke)

- Snapshot-only: no live scraping in CI (`--offline --snapshot-only` in smoke container).
- Providers config is pinned: `SMOKE_PROVIDERS_CONFIG=/app/config/providers.json`.
- Validation scope is explicit:
  - `snapshots validate --provider <id>` validates only requested providers.
  - `--all` skips missing snapshot dirs and reports a skip reason.
- No snapshot refresh in CI (`SMOKE_UPDATE_SNAPSHOTS=0`).
- Outputs are compared via smoke contract checks (`scripts/smoke_contract_check.py`).

## Case Study: Perplexity Snapshot Mismatch (Historical)

Symptom:
- Docker smoke gate failed after adding `perplexity` to `config/providers.json` without committed
  `data/perplexity_snapshots/` in the image.

Root cause:
- Snapshot validation was too broad (attempted to validate all configured providers),
  so missing snapshot directories caused a hard failure.

Fix behavior (current):
- CI smoke validates only the requested provider(s) (`openai` in docker smoke).
- `--all` now skips missing snapshot directories with an explicit reason.

## Reference Paths

- Workflow: `.github/workflows/ci.yml`
- Make targets: `Makefile`
- Smoke scripts:
  - `scripts/verify_snapshots_immutable.py`
  - `scripts/replay_smoke_fixture.py`
  - `scripts/replay_run.py`
  - `scripts/publish_s3.py`
  - `scripts/cronjob_simulate.py`
  - `scripts/ci_artifact_contract_check.py`
  - `scripts/check_roadmap_discipline.py`
