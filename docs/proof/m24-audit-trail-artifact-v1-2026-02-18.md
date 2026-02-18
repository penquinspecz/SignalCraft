# M24 Audit Trail Artifact v1 (2026-02-18)

## Invariant
- Every finalized run emits `run_audit_v1.json` under the candidate-scoped run artifacts directory.
- Emission happens on success and failure finalize paths because write occurs inside `_finalize(...)`.
- Artifact content is canonical JSON (`sort_keys=True`, compact separators) and schema-validated before write.

## Schema + Artifact Paths
- Schema: `schemas/run_audit.schema.v1.json`
- Artifact path pattern:
  - Local/default candidate (legacy-compatible): `state/runs/<run_id_sanitized>/artifacts/run_audit_v1.json`
  - Non-local candidate: `state/candidates/<candidate_id>/runs/<run_id_sanitized>/artifacts/run_audit_v1.json`

## Contract Fields
- `candidate_id`
- `trigger_type` (`manual|cron|replay`)
- `actor` (best-effort, non-secret identifier; fallback `unknown`)
- `profile_hash` (current candidate profile hash; nullable if profile missing)
- `profile_hash_previous` (optional; only present when previous run hash exists and differs)
- `config_hashes` (scoring/profiles/providers/config fingerprint hashes)
- `timestamp_utc` (taken from run telemetry `started_at`)

## Replay + Determinism Notes
- `timestamp_utc` uses the run's existing `started_at` telemetry value instead of introducing a new wall-clock field.
- Replay semantics remain bounded: no nondeterministic ordering is introduced; payload key ordering is canonical.
- Trigger type defaults to `manual` unless `JOBINTEL_TRIGGER_TYPE` explicitly sets `cron` or `replay`.

## Validation Commands
```bash
make lint
make ci-fast
make gate
```
