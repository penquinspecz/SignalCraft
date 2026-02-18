# Threat Model v1 (Milestone 22)

Date: 2026-02-17
Scope: SignalCraft deterministic pipeline, dashboard API, and artifact/read-path systems.
Non-goals: architecture rewrite, auth/RBAC introduction.

## System Context
SignalCraft ingests provider data, writes deterministic run artifacts, indexes run metadata in SQLite, and exposes bounded read APIs for run inspection.

Primary security properties:
- Deterministic, replayable artifact outputs.
- Fail-closed network egress and artifact read boundaries.
- Candidate namespace isolation (`candidate_id`) for run/state surfaces.

## Trust Boundaries

| Boundary | Trusted Inputs | Untrusted Inputs | Key Assets |
|---|---|---|---|
| CLI user | local operator flags/env | arbitrary local env values, malformed args | run orchestration, state writes |
| Dashboard API | internal API code/schema checks | HTTP query/path params (`run_id`, `candidate_id`, artifact name) | run metadata/artifacts, latest pointers |
| Provider registry config | versioned config/schema | config drift, malformed provider entries | provider allowlists, modes, policy provenance |
| Network egress | Network Shield policy allowlists | remote URLs/redirects/DNS | scrape/provenance inputs |
| Artifact storage | schema-validated writers | local FS tampering, stale/corrupt files | run_report/run_summary/run_health/provider availability |
| SQLite index | deterministic rebuild + append model | db corruption/manual mutation | latest/history read paths |

## Attack Surface Review
- CLI + pipeline scripts under `scripts/` and `src/ji_engine/pipeline/runner.py`.
- Dashboard endpoints in `src/ji_engine/dashboard/app.py`.
- Egress enforcement in `src/ji_engine/utils/network_shield.py`.
- Artifact read/write contracts in `src/ji_engine/artifacts/catalog.py`, `schemas/*.json`, and runner artifact writers.
- Index and run resolution in `src/ji_engine/run_repository.py`.

## Threat Categories

### SSRF / Egress bypass
- Control: host/domain allowlists + DNS/IP classification + redirect revalidation + byte caps in `safe_get_text`.
- Evidence: `src/ji_engine/utils/network_shield.py`, `tests/test_network_shield.py`, `tests/test_network_egress_shield_v1.py`.
- Residual risk: policy misconfiguration in provider config can permit broader egress than intended.
- Severity: P1.

### Artifact poisoning (invalid/unexpected payloads)
- Control: schema validation at write-time and API boundary validation/category enforcement.
- Evidence: `src/ji_engine/pipeline/runner.py`, `src/ji_engine/dashboard/app.py`, `tests/test_artifact_model_v2.py`.
- Residual risk: direct filesystem tampering can still place malformed files (detected at read-time, not prevented at rest).
- Severity: P2.

### Path traversal
- Control: strict artifact key mapping from index + `..`/absolute path rejection + repository path resolution guard.
- Evidence: `src/ji_engine/dashboard/app.py`, `src/ji_engine/run_repository.py`, `tests/test_dashboard_app.py`, `tests/test_run_repository.py`.
- Residual risk: relies on index integrity + resolver checks; no arbitrary path input accepted by API.
- Severity: P2.

### Index corruption / stale index
- Control: deterministic rebuild, fallback scan, corruption recovery path.
- Evidence: `src/ji_engine/run_repository.py`, `tests/test_run_repository.py`.
- Residual risk: local write access can force repeated rebuild fallback and degrade performance.
- Severity: P2.

### Log / secret leakage
- Control: redaction scanners (`scan_text_for_secrets`, `scan_json_for_secrets`) + proof-bundle secret guards/redaction.
- Evidence: `src/ji_engine/utils/redaction.py`, `src/ji_engine/proof/bundle.py`, `tests/test_redaction_scan.py`, `tests/test_redaction_guard.py`, `tests/test_runner_redaction_enforcement.py`.
- Residual risk: runner redaction is warn-only unless `REDACTION_ENFORCE=1`; default is not fail-closed.
- Severity: P1.

### Multi-candidate data bleed
- Control: candidate-scoped run/state roots and candidate-aware resolver paths in repository/dashboard.
- Evidence: `src/ji_engine/config.py`, `src/ji_engine/run_repository.py`, `src/ji_engine/dashboard/app.py`, `tests/test_candidate_namespace.py`, `tests/test_candidate_state_contract.py`, `tests/test_run_repository.py`.
- Residual risk: legacy fallback paths for `local` require continued careful handling.
- Severity: P1.

## Findings (v1)
- P1: Secret-like payload guard in runner is not fail-closed by default (`REDACTION_ENFORCE` gate).
- P1: Candidate isolation depends on strict `candidate_id` sanitation and resolver discipline; continue to treat direct path joins as forbidden.
- P2: Artifact/index tampering is detected/fail-closed at read time, but local host compromise can still poison files at rest.
- P2: Dependency vulnerability checks are advisory-service dependent and can be unavailable transiently.

## Immediate Hardening (No architecture change)
- Keep `REDACTION_ENFORCE=1` enabled in production-like environments.
- Track default fail-closed follow-up in issue #167: https://github.com/penquinspecz/SignalCraft/issues/167
- Keep Network Shield tests mandatory in CI.
- Keep repository-only run/artifact resolution as non-negotiable.
- Keep candidate-aware endpoint tests in CI for all new read paths.
