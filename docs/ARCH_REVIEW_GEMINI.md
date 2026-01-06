# Architecture Review (Gemini) – Execution Checklist

This document translates the Gemini architecture review into concrete, testable work items.
Each item is scoped, has acceptance criteria, and can be implemented independently.

---

## Recommendations (10)

### 1. Failure alerting for the pipeline
- Context:
  run_daily.py alerts on success (new/changed jobs) but not on failure. If a stage crashes, the run may fail silently.
- Proposed change:
  Wrap each stage execution in try/except. On exception, send a Discord webhook message:
  "Job Pipeline FAILED" including stage name and error summary. Ensure lock cleanup still runs.
- Acceptance criteria:
  - Any stage failure exits non-zero.
  - A failure alert is sent unless --no_post is set.
  - Lock file is always removed on failure.
- Files touched:
  scripts/run_daily.py (and any shared Discord helper)
- Test/Verification commands:
  - python -m py_compile scripts/run_daily.py
  - Force a failure (e.g., missing input file) and run:
    python scripts/run_daily.py --profiles cs --no_post
- Status:
  TODO

---

### 2. Remove remaining sys.path bootstrap hacks
- Context:
  Several scripts historically used sys.path.insert to make imports work.
- Proposed change:
  Make the repo installable in editable mode and rely on normal imports:
  pip install -e .
- Acceptance criteria:
  - No script relies on sys.path.insert for normal execution.
  - All scripts run from repo root with venv active.
- Files touched:
  scripts/*.py, packaging config (pyproject.toml if needed)
- Test/Verification commands:
  - pip install -e .
  - python scripts/run_daily.py --profiles cs --us_only --no_post
- Status:
  TODO

---

### 3. Centralize all file paths in config
- Context:
  Hardcoded data/openai_*.json paths create brittle coupling between stages.
- Proposed change:
  Ensure all stage inputs/outputs come from ji_engine.config helpers.
- Acceptance criteria:
  - No hardcoded data/openai_* paths outside config.
  - Scripts accept CLI overrides but default to config paths.
- Files touched:
  src/ji_engine/config.py, affected scripts
- Test/Verification commands:
  - rg "data/openai_" scripts src
  - python scripts/run_daily.py --profiles cs,tam,se --us_only --no_post
- Status:
  PARTIAL

---

### 4. Reduce "bash-in-python" orchestration
- Context:
  run_daily.py orchestrates via subprocess calls and filesystem side effects.
- Proposed change:
  Option A (near-term):
  Keep subprocesses but make all inputs/outputs explicit and validated.
- Acceptance criteria:
  - Each stage validates required input files exist and are fresh.
  - run_daily.py passes explicit --in/--out args to each stage.
- Files touched:
  scripts/run_daily.py, stage scripts
- Test/Verification commands:
  - Delete an expected input file and confirm failure alert fires.
- Status:
  TODO

---

### 5. Harden Ashby GraphQL error handling
- Context:
  Hardcoded GraphQL queries may break if Ashby changes schema.
- Proposed change:
  Ensure fetch_job_posting never crashes the pipeline on 4xx/5xx responses.
- Acceptance criteria:
  - API errors result in enrich_status = failed or unavailable.
  - Enrichment continues for other jobs.
- Files touched:
  src/ji_engine/integrations/ashby_graphql.py
  scripts/enrich_jobs.py
- Test/Verification commands:
  - Simulate bad job ID and run enrichment.
- Status:
  VERIFY

---

### 6. Harden job ID extraction assumptions
- Context:
  Enrichment assumes apply_url contains a UUID.
- Proposed change:
  Add explicit fallback behavior:
  - If job ID cannot be extracted, mark unavailable with reason.
- Acceptance criteria:
  - Jobs without UUID do not crash enrichment.
  - enrich_status and enrich_reason are explicit.
- Files touched:
  scripts/enrich_jobs.py
- Test/Verification commands:
  - Modify one apply_url to a non-UUID format and run enrichment.
- Status:
  TODO

---

### 7. Containerize the pipeline
- Context:
  launchd and macOS environments are brittle; Docker would stabilize execution.
- Proposed change:
  Add Dockerfile with WORKDIR and mount ./data as a volume.
- Acceptance criteria:
  - docker build succeeds.
  - docker run produces ranked outputs.
- Files touched:
  Dockerfile, docs
- Test/Verification commands:
  - docker build -t jobintel .
  - docker run --rm -v "$PWD/data:/app/data" jobintel \
    python scripts/run_daily.py --profiles cs --us_only --no_post
- Status:
  TODO

---

### 8. Golden master integration test
- Context:
  Unit tests exist; full-pipeline regression tests do not.
- Proposed change:
  Add tests/fixtures/full_run with snapshot inputs and expected outputs.
- Acceptance criteria:
  - pytest runs a deterministic full pipeline test.
  - Scoring drift causes test failure.
- Files touched:
  tests/, tests/fixtures/
- Test/Verification commands:
  - pytest -q
- Status:
  TODO

---

### 9. Structured logging
- Context:
  print() works but lacks timestamps and levels.
- Proposed change:
  Introduce logging with INFO/DEBUG levels.
- Acceptance criteria:
  - Logs include timestamps and stage names.
  - DEBUG logs are suppressed by default.
- Files touched:
  runners and key scripts
- Test/Verification commands:
  - Run daily and inspect logs.
- Status:
  LATER

---

### 10. Scraping hygiene improvements
- Context:
  Hardcoded User-Agent and regex-based HTML stripping are fragile.
- Proposed change:
  Optional improvements: rotating UA list, consistent BeautifulSoup usage.
- Acceptance criteria:
  - No regression in scraping success.
- Files touched:
  scripts/enrich_jobs.py, HTML helpers
- Test/Verification commands:
  - Full pipeline run.
- Status:
  LATER

---

## Architecture Areas (5)

### Area 1: Orchestration model
- Context:
  Subprocess isolation is good; implicit file passing is brittle.
- Proposed change:
  Choose explicit IO contracts or library calls.
- Acceptance criteria:
  - One clear orchestrator contract.
- Status:
  TODO

---

### Area 2: Reliability and failure modes
- Context:
  Failures can be silent; lock files may linger.
- Proposed change:
  Failure alerting and guaranteed cleanup.
- Acceptance criteria:
  - Every failure produces a visible signal.
- Status:
  TODO

---

### Area 3: Security and privacy
- Context:
  Public data, but path hacks and logging risks exist.
- Proposed change:
  Remove sys.path hacks; never log secrets.
- Acceptance criteria:
  - No secrets in logs.
- Status:
  TODO

---

### Area 4: Packaging and deployment
- Context:
  launchd cwd issues; environment drift.
- Proposed change:
  Container-based execution path.
- Acceptance criteria:
  - Reproducible run in Docker.
- Status:
  TODO

---

### Area 5: Testing and determinism
- Context:
  Scoring logic must not drift silently.
- Proposed change:
  Golden master integration tests.
- Acceptance criteria:
  - pytest catches scoring changes.
- Status:
  TODO