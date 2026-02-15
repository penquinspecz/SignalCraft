# Post-Merge Phase 2 Hardening Receipt (Security + Determinism)

Date: 2026-02-15  
Branch audited: `main`  
Main HEAD: `4486ec7169419cc0e4bb16cefdabc746159ec750`  
Python: `3.14.3`

## Landed PRs in the #130-#135 sequence

- `#130` merged: docs roadmap security/indexing DoD
- `#131` merged: Network Shield v1
- `#132` merged: pipeline refactor (runner/stages architecture)
- `#133` merged: run-index read-path adoption into pipeline layer
- `#134` and `#135` closed after stacked-base deletion; equivalent content landed via:
  - `#136` (replacement for `#134`) merged
  - `#137` (replacement for `#135`) merged

## Verification Commands and Status

Executed on `main` (up to date with `origin/main`):

- `make format`: pass
- `make lint`: pass
- `make ci-fast`: pass (`621 passed, 15 skipped`)
- `make gate`: pass
  - Snapshot immutability: pass (`scripts/verify_snapshots_immutable.py`)
  - Replay smoke: pass (`scripts/replay_smoke_fixture.py`, `mismatched=0 missing=0`)

Execution note:

- Initial `make ci-fast` attempt failed due to local environment leakage (`AWS_PROFILE=jobintel-deployer` present); rerun after unsetting `AWS_PROFILE`/`AWS_DEFAULT_PROFILE` passed cleanly. No code changes were required for this.

## Determinism Posture (Unchanged)

Determinism remains enforced by both implementation and gates:

- Ordered outputs and stable contracts are guarded by the existing deterministic test suite (`make ci-fast`).
- Replay determinism is explicitly validated in gate via replay smoke (`PASS: all artifacts match run report hashes`).
- Snapshot immutability is explicitly validated in gate via fixed hash checks over snapshot fixtures.
- No snapshot fixture mutation occurred during this receipt generation.

## Network Shield v1 Posture

Shield location and policy implementation:

- Core shield logic resides in `src/ji_engine/utils/network_shield.py`.
- Call sites across providers/snapshots/pipeline include preflight validation and final URL validation behavior.
- Guard semantics in place:
  - fail-closed destination validation
  - DNS/IP deny rules for local/private targets
  - redirect destination revalidation
  - bounded response size (`max_bytes`) on guarded fetch paths

Egress sweep evidence (exact scans run):

- `rg -n "requests\\.(get|post)\\(" src scripts`
- `rg -n "urllib\\.request\\.urlopen" src scripts`
- `rg -n "page\\.goto\\(" src scripts`
- `rg -n "http://169\\.254\\.169\\.254|127\\.0\\.0\\.1|localhost" -S src scripts`

Observed hits include expected guarded paths and local metadata endpoint references in runner (`127.0.0.1`/`localhost`), consistent with ECS metadata probing behavior.

## Pipeline Seam Posture

Control-plane seam and layering are in place:

- `scripts/run_daily.py` remains a thin shim.
- Orchestration remains in `src/ji_engine/pipeline/runner.py` and stage modules.
- Forbidden direct constant usage guard exists: `tests/test_pipeline_seam_forbidden_imports.py`.
- Guard is enforced as part of passing test runs in `make ci-fast` and `make gate`.

## Known Remaining Gaps (Observed, Not Invented)

- PR bookkeeping gap: `#134/#135` are closed (not merged) due to stacked base removal, but replacement PRs `#136/#137` are merged and represent landed content.
- Egress scan still reports direct network primitive call sites; these require continued review discipline to keep policy gating intact as code evolves.
- Existing Kubernetes dashboard PVC/storageclass mismatch issue remains outside this code receipt scope.

## Context Snapshot

Recent proof directory entries at receipt time:

- `onprem-ops-hardening-2026-02-13.md`
- `pr-candidate-namespace-readiness-2026-02-13.md`
- `pr-dashboard-read-hardening-readiness-2026-02-13.md`
- `pr-run-repository-seam-readiness-2026-02-13.md`
- `python-3.12-baseline.txt`
- `python-3.14-validation.txt`
- `release-v0.1.0.md`
- `stash0-archive-2026-02-13.md`
- `stash0-archive-2026-02-13.patch`
- `stash0-nuggets-deferred-2026-02-13.md`
