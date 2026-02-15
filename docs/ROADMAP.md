© 2026 Chris Menendez. Source Available — All Rights Reserved.
See LICENSE for permitted use.

# SignalCraft Roadmap

SignalCraft is a deterministic, reproducible career intelligence platform.

- **SignalCraft = product surface**
- **JIE = deterministic engine core**

This roadmap is the anti-chaos anchor.
We optimize for:

1) Deterministic outputs
2) Debuggability
3) Deployability
4) Incremental intelligence
5) Productization without chaos
6) Infrastructure portability (cloud + on-prem)

If a change doesn’t advance a milestone’s Definition of Done (DoD), it’s churn.

---

# Document Contract

This file is the plan. The repo is the truth.

Every merged PR must:
- Declare which milestone moved
- Include evidence paths (tests, logs, proof bundles)
- Keep “Current State” aligned with actual behavior
- Preserve determinism contracts and replay guarantees

---

# Non-Negotiable Guardrails

- One canonical pipeline entrypoint (`scripts/run_daily.py`)
- Determinism > cleverness
- Contract-driven artifacts (schema versioning is mandatory)
- Replayability must work offline
- Operational truth lives in artifacts
- AI is last-mile augmentation only (bounded, cached, fail-closed)
- No credentialed scraping
- Legal constraints enforced in design
- CI must prove determinism and safety properties
- Cloud runs must be replayable locally
- Multi-user must never become a rewrite: **namespace first, features later**
- Milestone completion requires receipts

---

# Legal + Ethical Operation Contract

SignalCraft is a discovery and alerting net, not a job board replacement.

Hard rules:
- Canonical outbound links always included
- UI-safe artifacts never replace original job pages
- Robots and policy decisions logged in provenance
- Per-host rate limits enforced
- Opt-out supported via provider tombstone
- Honest, stable User-Agent
- No paywall bypass or login scraping

Evidence expectations:
- Provenance includes scrape_mode + policy decision
- Provider availability reasons surfaced explicitly
- Artifact model ensures UI-safe outputs remain legally conservative

---

# Current State

Last verified: 2026-02-15 on commit `72892a3b71dc10e809a53acd09c75c89e554fb07` (local verification; see git + CI receipts)
Latest release: v0.1.0

Foundation exists:
- Deterministic scoring contract (versioned config + schema + replay checks).
  Evidence: `config/scoring.v1.json`, `schemas/scoring.schema.v1.json`, `docs/DETERMINISM_CONTRACT.md`, `tests/test_scoring_determinism_contract.py`.
- Replay + snapshot immutability gate is enforced in CI/local.
  Evidence: `scripts/replay_smoke_fixture.py`, `scripts/verify_snapshots_immutable.py`, `Makefile` target `gate`, `.github/workflows/ci.yml`.
- Provider platform guardrails are in place (schema validation, deterministic selection, authoring helpers, enablement checks).
  Evidence: `schemas/providers.schema.v1.json`, `src/ji_engine/providers/selection.py`, `scripts/provider_authoring.py`, `tests/test_provider_authoring.py`, `tests/test_provider_registry.py`.
- Candidate namespace contract + candidate CLI plumbing exists.
  Evidence: `src/ji_engine/config.py`, `src/ji_engine/candidates/registry.py`, `scripts/candidates.py`, `docs/CANDIDATES.md`, `tests/test_candidate_state_contract.py`.
- Run health + run summary artifacts are emitted and schema-validated.
  Evidence: `schemas/run_health.schema.v1.json`, `schemas/run_summary.schema.v1.json`, `scripts/run_daily.py`, `tests/test_run_health_artifact.py`, `tests/test_run_summary_artifact.py`.
- Local run index (SQLite) exists with deterministic read/list CLI.
  Evidence: `src/ji_engine/state/run_index.py`, `scripts/rebuild_run_index.py`, `src/jobintel/cli.py` (`runs list/show/artifacts`), `tests/test_run_index_sqlite.py`, `tests/test_jobintel_cli.py`.
- On-prem rehearsal has deterministic receipts and runbook wiring.
  Evidence: `scripts/onprem_rehearsal.py`, `schemas/onprem_rehearsal_receipt.schema.v1.json`, `ops/onprem/RUNBOOK_DEPLOY.md`, `tests/test_onprem_rehearsal.py`.
- CI has both fast feedback and full determinism gate.
  Evidence: `.github/workflows/ci.yml`, `Makefile` targets `ci-fast` and `gate`, `docs/CI_SMOKE_GATE.md`.

**Recent structural improvements (productization enablers):**
- Candidate namespace reservation (default `local`) to prevent future multi-user rewrite
- Dashboard artifact read hardening (bounded JSON reads + schema checks)
- RunRepository seam (filesystem-backed now; enables future indexing later)
- Provider default selection decoupled from hardcoded OpenAI (CLI/env/defaults/fallback precedence)
- Provider enablement workflow now fails closed when fixtures/manifest/metadata are missing
- Run receipt UX for one-command output discovery (`run_summary`, `run_health`, primary artifacts)

Phase 1 is real.

Recent receipts from `git log -n 30`:
- `361be61` refactor(providers): decouple default provider from openai
- `99d2ed7` feat(providers): add anthropic snapshot provider v1
- `006173a` feat(onprem): rehearsal receipt UX + deployment next-steps
- `e9f357b` feat(state): local run index sqlite v1 + runs list
- `dff8277` feat(cli): run receipt UX and primary artifact pointers
- `47c8ee3` chore(ci): add fast feedback job + keep full gate required
- `1867669` feat(providers): safe provider config append helper (disabled-by-default)
- `a6bba42` feat(run): add run_summary artifact v1 (single canonical output index)
- `3fbd76f` feat(providers): provider enablement workflow with guardrails
- `7fc07b5` fix(ci): include all pinned snapshot fixtures in docker test image

---

# Roadmap Philosophy

Fewer, thicker milestones.

Every milestone must:
- Produce artifacts
- Produce tests
- Produce receipts
- Reduce chaos
- Increase product clarity
- Increase infrastructure resilience

---

# NEW ROADMAP — Thick Milestones

## Milestone 10 — Provider Platform v1 (Boring Expansion) ◐

Goal: Provider expansion becomes boring and safe.
Status: ◐ Core guardrails are implemented; registry-hash provenance + tombstone semantics are not fully landed.
Evidence: `schemas/providers.schema.v1.json`, `scripts/provider_authoring.py`, `tests/test_provider_authoring.py`, `tests/test_provider_registry.py`, `scripts/verify_snapshots_immutable.py`.

Definition of Done
- [x] Versioned provider registry schema exists
- [ ] **Network Shield v1 (SSRF/Egress hardening) is required before any provider may set `live_enabled=true`**, including:
  - denylist coverage for `localhost`/`127.0.0.1`, RFC1918 ranges, and link-local metadata endpoints (for example `169.254.169.254`)
  - redirect revalidation on every hop
  - max-bytes streamed download cap enforcement
- [ ] Registry hash recorded in provenance
- [x] Provider config validated in CI (schema + invariants)
- [x] Snapshot fixtures enforced per provider (enabled snapshot providers)
- [ ] Provider tombstone supported (opt-out / takedown path)
- [x] At least 3 providers now run in snapshot mode from registry config (`openai`, `anthropic`, `cohere`, `huggingface`, `mistral`, `perplexity`, `replit`, `scaleai`)
- [x] No core pipeline modification required to add a provider (authoring + enablement tooling is config-driven)
- [x] Provider ordering deterministic across runs

Receipts Required
- Deterministic ordering tests
- Snapshot completeness enforcement tests
- Network Shield receipts/tests:
  - denylist tests for localhost/loopback, RFC1918, and `169.254.169.254`
  - redirect revalidation tests
  - streamed download max-bytes cap tests
- Proof doc in `docs/proof/`

---

## Milestone 11 — Artifact Model v2 (Legal + UI-Safe by Design) ◐

Goal: Legality + replayability enforced by shape.
Status: ◐ UI-safe and replay-safe schema contracts scaffolded; pipeline emission of v2 artifacts is deferred.
Evidence: `schemas/ui_safe_artifact.schema.v1.json`, `schemas/replay_safe_artifact.schema.v1.json`, `docs/ARTIFACT_MODEL.md`, `tests/test_artifact_model_v2.py`, `schemas/run_health.schema.v1.json`, `schemas/run_summary.schema.v1.json`, `tests/test_redaction_guard.py`, `tests/test_redaction_scan.py`.

Definition of Done
- [x] UI-safe artifact schema versioned
- [x] Replay-safe artifact schema versioned
- [x] UI-safe artifacts contain no raw JD text in run summary pointers
- [x] Redaction boundaries enforced by tests (stdout/logs included)
- [x] Retention policy documented (what is stored, for how long, why)
- [x] Artifact backward compatibility defined (and tested)
- [x] Artifact provenance includes provider policy decision + canonical URL (run report provenance by provider)

Receipts Required
- Schema validation suite
- Redaction + “no raw JD” test suite
- Proof doc

---

## Milestone 12 — Operations Hardening Pack v1 (Explicit Failure + Inspectability) ◐

Goal: Failure is explicit and inspectable.
Status: ◐ Run health taxonomy + summary + run inspection CLI landed; dedicated provider-availability artifact and explicit failure playbook receipts are still partial.
Evidence: `schemas/run_health.schema.v1.json`, `schemas/run_summary.schema.v1.json`, `scripts/run_daily.py`, `src/jobintel/cli.py`, `tests/test_run_health_artifact.py`.

Definition of Done
- [x] `failed_stage` always populated on failure
- [x] Cost telemetry always written (even on partial failure)
- [ ] Provider availability artifact generated every run
- [x] One-command run inspection tooling (human-friendly)
- [x] CI smoke matches real run structure
- [ ] Failure playbook updated
- [x] **Candidate namespace is treated as first-class (default `local`)**:
  - candidate_id flows through orchestration
  - artifacts + pointers do not collide across candidates
  - backward compatibility policy documented

Receipts Required
- Forced failure proof run (with artifacts)
- Artifact inspection proof
- Candidate isolation proof artifacts/tests

---

## Milestone 13 — Run Indexing v1 (Metadata Without Rewrites) ◐

Goal: Remove “filesystem-as-database” pain without abandoning artifacts.

Rationale: Artifacts stay as blobs. Indexing is metadata only.
Status: ◐ SQLite index, deterministic rebuild, and CLI run lookups are landed; full repository-only resolution coverage still needs finishing.
Evidence: `src/ji_engine/state/run_index.py`, `scripts/rebuild_run_index.py`, `docs/proof/m13-run-indexing-v1-2026-02-13.md`, `tests/test_run_index_sqlite.py`, `src/jobintel/cli.py`.

Definition of Done
- [ ] RunRepository seam is the only way to resolve runs (no scattered path-walking)
- [x] A minimal index exists for O(1) “latest run” + recent run listing:
  - Option A (preferred on-prem friendly): SQLite index in state (single-writer safe)
  - Option B (cloud friendly): DynamoDB / Postgres later (not required now)
- [x] Index is append-only and derived from artifacts (rebuildable)
- [x] Dashboard endpoints do not require directory scans for the common case
- [x] Index rebuild tool exists (deterministic)
- [ ] At least one real read path (`history`, `diff`, or `retention`) is migrated to SQLite-backed lookup instead of walking JSON files

Receipts Required
- Index rebuild proof
- Determinism proof: index rebuild yields identical results
- Dashboard performance sanity proof (basic benchmark notes)
- Read-path migration proof showing SQLite-backed resolution for at least one of: history/diff/retention

---

## Milestone 14 — AI Insights v1 (Grounded Intelligence, Bounded) ◐

Goal: Weekly insights are useful and bounded.
Status: ◐ Structured AI insights pipeline exists with deterministic cache keys; full milestone contract (explicit schemas + complete trend surfaces) is still in progress.
Evidence: `src/ji_engine/ai/insights_input.py`, `src/jobintel/ai_insights.py`, `tests/test_ai_insights.py`, `tests/test_insights_input.py`.

Definition of Done
- [ ] Deterministic input schema versioned
- [ ] 7/14/30 day trend analysis
- [ ] Skill token extraction from structured fields (not raw JD)
- [ ] Strict output schema enforcement
- [x] Cache keyed by input hash + prompt version
- [ ] “Top 5 Actions” section included
- [ ] No raw JD leakage

Receipts Required
- Two-run determinism proof
- Schema validation tests

---

## Milestone 15 — AI Per-Job Briefs v1 (Coaching Per Job, Deterministic Cache) ◐

Goal: Profile-aware coaching per job.
Status: ◐ Profile-hash + deterministic cache behavior is implemented; explicit standalone schema file contract is still pending.
Evidence: `src/jobintel/ai_job_briefs.py`, `tests/test_ai_job_briefs.py`, `scripts/run_daily.py` (`ai_accounting` fields).

Definition of Done
- [x] Candidate profile hash contract defined
- [ ] `ai_job_brief.schema.json` enforced
- [x] Cache keyed by job_hash + profile_hash + prompt_version
- [x] Cost accounting integrated
- [x] Deterministic hash stability verified
- [ ] Schema validation enforced in CI

Receipts Required
- Deterministic diff proof
- Cost artifact proof

---

## Milestone 16 — Explainability v1 (Make Scores Interpretable) ◐

Goal: Scores are explainable and stable.
Status: ◐ Explain-top outputs and penalty visibility exist in scorer output, but a formal `explanation_v1` artifact contract is not yet declared.
Evidence: `scripts/score_jobs.py`, `tests/test_score_jobs_explain_top.py`, `tests/test_score_jobs_top_n.py`.

Definition of Done
- [ ] `explanation_v1` structure implemented
- [x] Top contributing signals surfaced
- [x] Penalties visible
- [ ] Semantic contribution bounded + surfaced (if used)
- [x] Deterministic ordering enforced

Receipts Required
- Artifact snapshot proof
- Ordering tests

---

## Milestone 17 — Dashboard Plumbing v2 (Backend-First UI Readiness) ◐

Goal: Backend is UI-ready without becoming UI-first.
Status: ◐ `/version` endpoint and API contract documented; artifact index endpoints already stable.
Evidence: `src/ji_engine/dashboard/app.py`, `tests/test_dashboard_app.py`, `docs/DASHBOARD_API.md`, `scripts/dev/curl_dashboard_proof.sh`, `docs/proof/m17-api-boring-pack-2026-02-15.md`.

Definition of Done
- [x] `/version` endpoint
- [x] `/runs/latest` endpoint is candidate-aware (implemented as `/v1/latest?candidate_id=...`)
- [x] Artifact index endpoint(s) are stable and documented
- [x] API contract documented
- [ ] Optional deps isolated cleanly
- [x] Read-time validation is fail-closed and bounded

Receipts Required
- API proof doc
- Simulated UI proof (curl scripts + sample payloads)

---

## Milestone 18 — Release Discipline v1 (Releases Are Proof Events) ◐

Goal: Releases are evidence-backed.
Status: ◐ Release process and proof artifacts exist; changelog enforcement and full reproducible-build verification need explicit CI enforcement.
Evidence: `docs/RELEASE_PROCESS.md`, `docs/proof/release-v0.1.0.md`, `scripts/preflight_env.py`.

Definition of Done
- [x] Release checklist codified
- [x] Preflight validation script exists
- [ ] Changelog enforcement policy
- [x] Every release includes proof bundle
- [ ] Reproducible build instructions verified

Receipts Required
- One full release dry-run proof bundle

---

# INFRASTRUCTURE EVOLUTION

## Milestone 19 — AWS DR & Failover Hardening ◐

Goal: Cloud execution survives failure.
Status: ◐ AWS operational scripts/runbooks exist, but milestone-level DR receipts (versioning/lifecycle/rehearsal metrics) are not fully captured.
Evidence: `scripts/aws_*.py`, `ops/aws/`, `docs/OPS_RUNBOOK.md`.

Definition of Done
- [ ] S3 versioning enabled
- [ ] S3 lifecycle policy defined
- [ ] Backup bucket replication strategy documented
- [ ] Disaster recovery restore rehearsal executed
- [ ] RTO + RPO explicitly defined
- [ ] Infrastructure config versioned
- [ ] Recovery playbook tested

Receipts Required
- Restore rehearsal proof
- Recovery time measurement
- Backup verification artifact

---

## Milestone 20 — On-Prem Migration Contract (AWS → k3s) ◐

Goal: Migration is engineered, not improvised.
Status: ◐ On-prem deploy runbooks + deterministic rehearsal are in place; formal AWS-vs-onprem dual-run diff contract is still pending.
Evidence: `ops/onprem/RUNBOOK_DEPLOY.md`, `ops/onprem/RUNBOOK_DNS.md`, `scripts/onprem_rehearsal.py`, `schemas/onprem_rehearsal_receipt.schema.v1.json`.

Definition of Done
- [ ] Data migration plan documented
- [ ] Artifact compatibility verified
- [ ] Backwards compatibility test suite passes
- [x] Rollback plan documented
- [ ] Dual-run validation (AWS vs on-prem output diff)
- [ ] Zero artifact schema changes required
- [ ] Migration dry run executed

Receipts Required
- Side-by-side artifact diff proof
- Migration dry run log
- Rollback rehearsal doc

---

## Milestone 21 — On-Prem Stability Proof (Post-Migration) ⏸

Goal: On-prem becomes primary without chaos.
Status: ⏸ Foundational runbooks and rehearsal receipts exist, but 72-hour continuous stability proof is not yet complete.
Evidence: `ops/onprem/RUNBOOK_BORING_72H_PROOF.md`, `docs/proof/onprem-ops-hardening-2026-02-13.md`.

Definition of Done
- [ ] 72-hour continuous k3s run
- [ ] CronJob stability verified
- [ ] Storage durability verified
- [ ] Backup + restore rehearsal on-prem
- [ ] Resource utilization captured
- [ ] Determinism validated against AWS baseline
- [ ] Failure injection rehearsal (kill pod, restart node)

Receipts Required
- Stability logs
- Restore proof
- Deterministic diff proof

---

# GOVERNANCE & PRODUCTIZATION PREREQS

## Milestone 22 — Security Review Pack v1 (Audited Posture) ◐

Goal: Security posture is audited, not assumed.
Status: ◐ Security posture/runbooks and SSRF stance are documented; full formal threat-model + IAM review package remains incomplete.
Evidence: `SECURITY.md`, `docs/LEGAL_POSITIONING.md`, `ops/onprem/RUNBOOK_DNS.md`, `tests/test_redaction_guard.py`.

Definition of Done
- [ ] Threat model document created (multi-tenant aware)
- [ ] Attack surface review performed
- [x] Secrets handling reviewed + redaction tests enforced
  - Clarification: regex redaction is best-effort only, and is not the primary security control
  - Primary control: no secrets are written to artifacts/log bundles by construction
- [ ] Dependency audit completed
- [ ] Least-privilege IAM documented (AWS + on-prem)
- [x] Static analysis tool integrated
- [x] SECURITY.md aligned with reality
- [x] “User-supplied URL/provider” policy documented (SSRF/egress stance)

Receipts Required
- Threat model artifact
- Dependency audit report
- IAM review checklist
- Tests proving secrets are never serialized into run artifacts/log bundles

---

## Milestone 23 — Code Surface & Bloat Review (Entropy Reduction) ⏸

Goal: Eliminate entropy before adding product surfaces.
Status: ⏸ Not yet run as a focused milestone; only opportunistic cleanup has landed with feature work.
Evidence: no dedicated proof artifact yet.

Definition of Done
- [ ] Dead code removed
- [ ] Unused deps removed
- [ ] Duplicate logic consolidated
- [ ] File structure rationalized
- [ ] Public API boundaries clarified
- [ ] Complexity hotspots documented
- [ ] Size diff documented

Receipts Required
- Before/after LOC diff
- Dependency tree comparison
- Simplification proof doc

---

## Milestone 24 — Multi-User Plumbing v1 (Foundation + Isolation) ◐

Goal: Prepare for product without UI complexity.
Status: ◐ Candidate registry/schema/isolation are implemented with backward compatibility for `local`; audit trail depth is still partial.
Evidence: `schemas/candidate_profile.schema.v1.json`, `src/ji_engine/candidates/registry.py`, `scripts/candidates.py`, `tests/test_candidate_namespace.py`, `tests/test_candidate_state_contract.py`.

Definition of Done
- [x] `candidate_profile.schema.json` defined
- [x] candidate registry exists (CRUD via file/CLI only; no web UI required)
- [x] Candidate isolation enforced end-to-end (paths, pointers, index)
- [x] Cross-user leakage tests implemented
- [ ] Audit trail artifacts exist (who/what triggered run; profile hash change record)
- [x] Backward compatibility maintained for `local`
- [x] No authentication/UI implemented yet

Receipts Required
- Isolation test suite
- Audit trail proof artifacts
- Backward compat proof

---

# Phase 3 Preview (25–35)

Product surface comes after plumbing and security receipts:
- Authentication + authz (RBAC)
- Resume/LinkedIn ingestion (strict SSRF + egress policy)
- Profile UX + presets (seniority, role archetypes)
- Alerts + digests (daily/weekly)
- AI coaching expansion (bounded, opt-in, costed)
- Billing/cost attribution readiness
- Provider scaling + maintenance tooling
- UI (only after API is boring)

---

## Archive — Milestones 1–9 (Completed)

This archive is retained for historical continuity; the active roadmap above remains canonical. These milestones are completed and superseded by the current structure and PR receipts.

# ARCHIVE — Milestones 1–9 (Completed / Superseded)

**Archive rule:** These milestones are “done enough” for Phase 1.  
Do not reopen unless a regression threatens determinism, replayability, or deployability.

## Milestone 1 — Daily run deterministic & debuggable (Local + Docker + CI) ✅
**Receipts:** see `docs/OPERATIONS.md`, CI smoke contracts, snapshot helpers.
- [x] `pytest -q` passes locally/CI
- [x] Docker smoke produces ranked outputs + run report
- [x] Exit codes normalized
- [x] Snapshot debugging helpers (`make debug-snapshots`)
- [x] CI deterministic artifact validation

## Milestone 2 — Determinism Contract & Replayability ✅
**Receipts:** `docs/RUN_REPORT.md`, `scripts/replay_run.py`, tests covering selection reasons + archival + `--recalc`.
- [x] Run report explains selection
- [x] Schema contract documented
- [x] Selected inputs archived per run
- [x] Replay workflow + hash verification

## Milestone 3 — Scheduled run + object-store publishing (K8s CronJob first) ◐
**Status:** Core mechanics are present (CronJob manifests + publish tooling + tests), but external “real bucket/live scrape” proof receipts are not archived in-repo.
**Receipts:** `scripts/publish_s3.py`, `scripts/verify_s3_publish.py`, `ops/k8s/overlays/onprem-pi/`, `tests/test_publish_*.py`.
- [x] CronJob runs end-to-end
- [x] S3 publish plan + offline verification
- [ ] Real bucket publish verified (+ latest pointers)
- [ ] Live scrape proof in-cluster
- [x] Politeness/backoff/circuit breaker enforced

## Milestone 4 — On-Prem primary + Cloud DR (proven once; stability pending) ◐
**Status:** Partially complete: backup/restore + cloud DR proven once, on-prem 72h stability not yet proven.
**Receipts:** `ops/onprem/RUNBOOK_DEPLOY.md`, `ops/onprem/RUNBOOK_DNS.md`, `docs/proof/onprem-ops-hardening-2026-02-13.md`.
- [x] Backup/restore rehearsal documented
- [ ] DR rehearsal end-to-end (bring up → restore → run → teardown)
- [ ] On-prem 72h stability receipts (blocked by hardware timing)

## Milestone 5 — Provider Expansion (config-driven, offline proof) ◐
**Status:** Offline multi-provider proof exists; “fully config-driven provider registry” still needs consolidation/hardening as a single coherent milestone (see Milestone 10 below).
**Receipts:** `docs/proof/m5-offline-multi-provider-2026-02-11.md`

## Milestone 6 — History & intelligence (identity, dedupe, user state) ✅
**Receipts:** `src/ji_engine/history_retention.py`, tests, `docs/OPERATIONS.md`.
- [x] Stable job identity + identity-based diffs
- [x] Retention rules enforced
- [x] User state overlay affects outputs and alerts

## Milestone 7 — Semantic Safety Net (deterministic) ✅ (Phase 1 scope)
**Receipts:** `docs/proof/m7-semantic-safety-net-offline-2026-02-12.md`, tests.
- [x] Deterministic embedding backend (hash backend) + cache
- [x] Sidecar + boost modes
- [x] Thresholds testable/documented
- [x] Evidence artifacts produced

## Milestone 8 — Hardening & scaling (Phase 1 subset done) ◐
**Status:** Several elements exist (cost guardrails, provider availability reasons, observability basics), but consolidation is needed (see Milestone 12).
- [x] Cost guardrails + costs artifact
- [x] Provider unavailable reasons surfaced
- [x] CI smoke gate failure modes documented
- [ ] Full “operational hardening pack” milestone still needed

## Milestone 9 — Multi-user (deferred to Phase 3) ⏸
**Status:** intentionally deferred; do not start UX/product complexity until Phase 2/3 tranche.

---
