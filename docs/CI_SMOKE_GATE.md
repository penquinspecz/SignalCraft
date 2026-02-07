# CI Smoke Gate Contract

This document is the operational contract for `.github/workflows/ci.yml`.
It describes exactly what CI runs, what each step proves, and how to debug failures quickly.

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

Source: `.github/workflows/ci.yml`.

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

### 4) Roadmap guard (warn-only) contract

- Runs `scripts/check_roadmap_discipline.py`.
- Findings are logged but do not fail CI yet (`continue-on-error: true`).

Source: `.github/workflows/ci.yml`.

## Failure Modes And What To Inspect

### Failure: `make gate-ci` in `pytest -q`

Inspect:

```bash
.venv/bin/python -m pytest -q -x
.venv/bin/python -m pytest -q <failing_test_path>::<test_name> -vv
```

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

### Failure: `deps-check` / stale lock contract

Inspect:

```bash
make deps-check
make deps-sync
git diff -- requirements.txt requirements-dev.txt
```

If local network is unavailable, local export may use deterministic installed-env fallback.
CI remains strict and fail-closed.

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

### Docker truth build path

```bash
DOCKER_BUILDKIT=1 docker build --no-cache --build-arg RUN_TESTS=1 -t jobintel:tests .
```

## Reference Paths

- Workflow: `.github/workflows/ci.yml`
- Make targets: `Makefile`
- Smoke scripts:
  - `scripts/verify_snapshots_immutable.py`
  - `scripts/replay_smoke_fixture.py`
  - `scripts/replay_run.py`
  - `scripts/publish_s3.py`
  - `scripts/cronjob_simulate.py`
  - `scripts/check_roadmap_discipline.py`
