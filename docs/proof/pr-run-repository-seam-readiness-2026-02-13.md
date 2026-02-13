# PR Receipt: RunRepository Seam Merge Readiness (2026-02-13)

Branch under review: `codex/arch-run-repository-seam`

## Scope Reconciled
- New run storage seam via `RunRepository` interface.
- `FileSystemRunRepository` implementation with deterministic list ordering and candidate namespace support.
- Dashboard and run-loading utilities updated to depend on repository seam instead of direct path walking.
- Duplicate path-walking helpers reduced where superseded by repository methods.

## Evidence Paths
- `src/ji_engine/run_repository.py`
- `src/ji_engine/dashboard/app.py`
- `src/ji_engine/ai/insights_input.py`
- `src/jobintel/ai_insights.py`
- `src/jobintel/ai_job_briefs.py`
- `tests/test_run_repository.py`

## Reconciliation Notes
- Added candidate_id threading (default `local`) through AI run-loading scripts/utilities.
- Seam remains filesystem-only (no DB introduced), preserving current behavior.
