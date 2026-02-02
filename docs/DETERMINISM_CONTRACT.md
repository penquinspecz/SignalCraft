# Determinism Contract

## 1) What “deterministic” means in this repo

Deterministic means **byte-identical outputs given the same inputs**. That includes:
- Stable ordering of lists and keys before serialization.
- Canonical JSON/CSV output formatting.
- Fixed execution environment where relevant (Docker no-cache is the source of truth).

If the inputs (snapshots, config, profile) are unchanged, the ranked outputs and run report hashes must be identical.

## 2) Snapshot immutability rule

Pinned snapshots under `data/*_snapshots/` are **immutable fixtures**. Tests and runs must not mutate them.

Guardrails:
- Pre-commit hook blocks snapshot commits unless explicitly allowed.
- Snapshot immutability verifier fails if bytes drift.

Override workflow (intentional refresh only):
- Set `ALLOW_SNAPSHOT_CHANGES=1` when committing a snapshot refresh.
- Update the snapshot bytes manifest to reflect new pinned bytes.

Why: snapshot drift makes “local green / Docker red” failures, and breaks golden reproducibility.

## 3) Run report + replay verification

Run reports capture inputs/outputs and their hashes. Replay verification re-computes hashes and compares.

Command:
```bash
python scripts/replay_run.py --run-id <run_id> --strict
```

Exit codes:
- `0` success (all hashes match)
- `2` missing artifacts or mismatches
- `>=3` runtime errors

Replay never regenerates artifacts. It only verifies recorded hashes.

## 4) S3 publish verification contract

Publish verification asserts that objects exist for each verifiable artifact recorded in the run report.

Command:
```bash
python scripts/verify_published_s3.py --bucket <bucket> --run-id <run_id> --verify-latest
```

Exit codes:
- `0` success
- `2` missing objects or validation failure
- `>=3` runtime errors

## 5) Gates

Local fast gate:
```bash
make gate-fast
```

Docker truth gate:
```bash
docker build --no-cache --build-arg RUN_TESTS=1 -t jobintel:tests .
```

## 6) Common failure modes + fixes (top 5)

1) **Snapshot bytes drift**
   - Symptom: immutability check fails or Docker/local mismatch.
   - Fix: restore snapshots to HEAD; refresh only with explicit workflow.

2) **Live scraping in golden tests**
   - Symptom: “Scraped N jobs” count changes or hash mismatch.
   - Fix: enforce `CAREERS_MODE=SNAPSHOT` and `--offline` in tests.

3) **Ordering nondeterminism**
   - Symptom: same data, different hash; CSV/JSON changes.
   - Fix: sort lists and keys before serialization.

4) **Environment drift (locale/time)**
   - Symptom: Docker vs local mismatch with same inputs.
   - Fix: use Docker no-cache; keep `TZ=UTC` and `PYTHONHASHSEED=0`.

5) **Golden manifest mismatch**
   - Symptom: golden hash mismatch after deterministic change.
   - Fix: update golden fixtures only after confirming snapshot-only mode.

## 7) CI vs local parity notes

- Docker no-cache build is the source of truth.
- Local fast gate is for quick feedback; it must match Docker behavior.
- If CI is flaky, rerun the workflow or wait for GitHub Actions recovery.
