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

# Product Thesis (2026)

SignalCraft product direction is now explicit:

- **Temporal Intelligence > Matching**
- Matching remains useful, but the primary product truth is longitudinal change:
  how postings evolve, what skills drift, and where role requirements shift over
  time.
- Deterministic provenance and artifact-backed diffs are required for every
  longitudinal claim.
- Provider expansion is treated as a first-class product capability through the
  onboarding factory model (policy evaluation, scaffolding, receipts, and
  auditable enablement), not ad hoc scraping.

This thesis is additive and does not reorder milestone blocks below.

---

# Current State

Last verified: 2026-03-01 on commit `ea3a7a2c2519da010c643d191cca48aad736f07a` (mainline verification checks were confirmed green on this SHA.)
Latest product release: v0.2.0
Relevant milestone releases: m19-20260222T201429Z, m19-20260222T181245Z

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
- Network Shield v1 + unified egress policy gates are enforced across provider/snapshot/pipeline fetch paths (fail-closed, redirect revalidation, bounded reads).
  Verified by `docs/proof/post-merge-phase2-hardening-2026-02-15.md`, `src/ji_engine/utils/network_shield.py`, `tests/test_network_shield.py`, `tests/test_network_egress_shield_v1.py`.
- Artifact model v2 schemas + dashboard API boundary enforcement are landed.
  Verified by `docs/proof/m11-artifact-model-v2-enforcement-2026-02-15.md`, `docs/proof/m11-api-ui-safe-enforcement-2026-02-15.md`, `src/ji_engine/artifacts/catalog.py`, `src/ji_engine/dashboard/app.py`, `tests/test_artifact_model_v2.py`, `tests/test_dashboard_app.py`.
- Operations hardening receipts expanded with provider availability artifact and failure playbook receipts.
  Verified by `docs/proof/m12-provider-availability-artifact-2026-02-15.md`, `docs/proof/m12-failure-playbook-receipts-2026-02-14.md`, `docs/OPS_RUNBOOK.md`, `tests/test_run_health_artifact.py`.
- Run indexing/read-path migration advanced: RunRepository-only run resolution and SQLite-backed history read path landed.
  Verified by `docs/proof/m13-no-run-filesystem-scan-outside-tests-2026-02-15.md`, `docs/proof/m13-readpath-history-sqlite-2026-02-15.md`, `src/ji_engine/run_repository.py`, `scripts/report_changes.py`, `tests/test_m13_no_run_filesystem_scan_repo_wide.py`, `tests/test_run_repository.py`.
- Dashboard plumbing is now API-boring: `/version`, artifact index endpoint, bounded artifact serving, and smoke receipts are landed.
  Verified by `docs/proof/m17-api-boring-pack-2026-02-15.md`, `docs/proof/m17-artifact-index-endpoint-2026-02-14.md`, `docs/proof/m17-api-boring-pack-smoke-negative-2026-02-15.md`, `docs/proof/p1-artifact-download-size-cap-2026-02-17.md`, `docs/DASHBOARD_API.md`.
- PR governance enforcement: labels (provenance, type, area), milestone required, provenance label-only (no `[from-composer]` in titles).
  Verified by `docs/LABELS.md`, `docs/proof/provenance-always-enforced-20260222T211953Z.md`, `.github/workflows/pr-governance.yml`.
- Provider onboarding factory baseline is in place via schema-backed provider registry, authoring/scaffold tooling, and policy-aware enablement checks.
  Verified by `schemas/providers.schema.v1.json`, `scripts/provider_authoring.py`, `src/ji_engine/providers/selection.py`, `tests/test_provider_authoring.py`, `tests/test_provider_registry.py`.
- Release governance now enforces canonical, self-contained release body structure with tier-aware product validation (major vs minor/patch) before publish.
  Verified by `scripts/release/render_release_notes.py`, `scripts/release/validate_release_body.py`, `.github/workflows/release-ecr.yml`,
  `docs/RELEASE_TEMPLATE_PRODUCT.md`, `docs/RELEASE_TEMPLATE_MILESTONE.md`,
  `docs/proof/release-body-policy-20260228T031653Z.md`, `docs/proof/release-workflow-tier-enforcement-20260228T032512Z.md`, `docs/proof/release-body-normalization-20260228T032035Z.md`.
- M19 DR proof discipline: cost guardrails (validate-only default), branch auto-delete, cleanup rollup receipts.
  Verified by `docs/proof/20260222T211723Z-cleanup-rollup.md`, `scripts/ops/dr_drill.sh`, `scripts/ops/dr_validate.sh`.

---

# Roadmap Truth Sync

- Milestone metadata governance is enforced programmatically (labels +
  milestones), not by manual UI-only process.
- Milestones have been retroactively aligned so historical PRs map to roadmap
  `M##` milestones where deterministically inferable.
- Catch-all milestones (`Infra & Tooling`, `Docs & Governance`,
  `Backlog Cleanup`) were removed after rehoming and verification.
- Ambiguous historical items are explicitly parked in deterministic triage
  milestone buckets rather than hidden in catch-all milestones.

---

# Phase 2: Hardening & Correction Epoch

This section is an additive overlay for near-term correction work. It does not
renumber, reorder, or replace existing milestone blocks in this document.

## Correction Track Principles

- No determinism regression.
- No CI loosening.
- No silent contract changes; any artifact/API shape change requires schema
  versioning and explicit migration notes.
- Replay unchanged unless explicitly intended and receipted.
- Snapshot baseline unchanged unless explicitly intended and receipted.
- Prefer surface reduction over feature growth.
- Security and correctness fixes take priority over new feature plumbing.
- **DR scope freeze during correction epoch:** no new DR feature work; only
  security/correctness fixes are in-scope.

## Gemini Review Concerns -> Roadmap Mapping

- DNS rebinding SSRF TOCTOU in network egress flow -> `Phase2-C1`
- Tar path traversal / tar slip in restore paths -> `Phase2-C2`
- Symlink/path traversal in run artifact resolution -> `Phase2-C3`
- PR governance automation gaps (label/milestone drift) -> `Phase2-C4`
- Warn-only or incomplete redaction enforcement posture -> `Phase2-C5`
- Snapshot/fixture growth and repository bloat risk -> `Phase2-C6`
- DR overinvestment / maintainability risk -> correction-epoch DR freeze +
  decomposition notes in `Phase2-C6`
- Filesystem-as-DB limits + multi-tenant concurrency pressure -> **Future
  Platform Phase (explicitly out of scope for correction epoch)**

## Recommended Sequence Lens (Additive Overlay)

Sequencing guidance only. This does not reorder milestone blocks.

- Tier 0: `Phase2-C1`, `Phase2-C2`, `Phase2-C3`
- Tier 1: `Phase2-C4`, `Phase2-C5`
- Tier 2: `Phase2-C6`
- Tier 3: Active product loop milestones (`M25`, `M28`, `M29`, `M34`)
- Tier 4: Future Platform Phase (state backend migration, queue orchestration,
  full multi-tenant auth/RBAC)

## Correction Track Items (Non-Colliding IDs)

### Phase2-C1 — Network Shield DNS Pinning + Redirect TOCTOU Closure

Goal: Ensure each request hop validates and connects to a pinned destination
without DNS rebinding bypass.
Status: Planned / in-flight correction.
PR mapping: `#252` (security: SSRF hardening).

Definition of Done
- [ ] Resolve and validate destination exactly once per hop.
- [ ] Redirect hops revalidated under the same pinned-connect contract.
- [ ] HTTPS behavior remains fail-closed (no TLS verification weakening).
- [ ] Negative regression tests prove TOCTOU rebinding attempts are blocked.

Receipts Required
- Network shield tests proving single-resolution + redirect-safe enforcement
- Proof note in `docs/security/` or equivalent operations docs

### Phase2-C2 — Restore Safe Extraction (Tar Slip Guardrails)

Goal: Reject traversal/non-regular archive members in restore flows.
Status: Planned / in-flight correction.
PR mapping: `#253` (security: safe extract).

Definition of Done
- [ ] Restore extraction rejects absolute paths and `..` traversal.
- [ ] Symlink/hardlink and non-regular members are rejected by default.
- [ ] Permission normalization avoids unsafe bit preservation.
- [ ] Negative tests confirm no writes outside destination root.

Receipts Required
- Restore safety tests with malicious archive fixtures
- Ops note confirming extraction policy

### Phase2-C3 — Run Artifact Path Hardening (Traversal + Symlink Safety)

Goal: Artifact resolution is provably bounded to run/candidate roots.
Status: Planned / in-flight correction.
PR mapping: `#254` (security: artifact path hardening).

Definition of Done
- [ ] Relative path normalization rejects absolute and traversal inputs.
- [ ] Symlink traversal attempts are rejected.
- [ ] Open-path behavior is no-follow (`O_NOFOLLOW` where available, explicit
  symlink rejection fallback otherwise).
- [ ] Tests cover both allowed normal paths and blocked symlink escape cases.

Receipts Required
- Run repository security tests
- Proof note describing no-follow strategy and platform fallback behavior

### Phase2-C4 — PR Governance Automation Consistency

Goal: Required PR metadata is enforced programmatically, deterministically.
Status: Planned / in-flight correction.
PR mapping: `#256` (governance applier), `#257` (labeler determinism),
`#258` (milestone sync).

Definition of Done
- [ ] Programmatic tooling can ensure required governance labels + milestone.
- [ ] Label assignment remains deterministic (single provenance, single type,
  >=1 area).
- [ ] Required roadmap milestone IDs are syncable via repo-owned tooling.
- [ ] Verification path matches `pr-governance` CI contract exactly.

Receipts Required
- CLI outputs showing pass/fail verification behavior
- Docs updates in `docs/LABELS.md` with usage guidance

### Phase2-C5 — Redaction Enforcement Policy Clarification

Goal: Move redaction posture from advisory ambiguity to explicit fail-closed
mode policy where required.
Status: Planned.

Definition of Done
- [ ] Runtime modes clearly define where strict redaction enforcement is
  mandatory.
- [ ] CI/gate tests prove strict mode behavior in user-visible/export paths.
- [ ] Docs explicitly state redaction is defense-in-depth, not perfect
  detection.

Receipts Required
- Mode matrix documentation
- Tests proving strict enforcement in governed modes

### Phase2-C6 — Fixture Growth Control + DR Scope Freeze Guardrail

Goal: Prevent entropy creep while preserving reproducibility and operator focus.
Status: Planned.

Definition of Done
- [ ] Fixture policy documents bounded in-repo fixtures and external corpus
  strategy with pinned manifests.
- [ ] Growth limits are enforced (or explicitly scheduled) in CI policy.
- [ ] DR scope freeze is explicit: no new DR features during correction epoch;
  security/correctness-only changes permitted.
- [ ] Decomposition notes separate durable DR proof artifacts from deferred
  platform work.

Receipts Required
- Fixture policy contract in docs
- CI/policy receipt and DR freeze/decomposition note

## Product Loop v0 (Near-Term Focus)

This is sequencing guidance only and does not reorder milestone blocks.

1. Milestone 25 — Provider Availability Always-On (M12 closeout)
2. Milestone 28 — Alerts & Digests v1
3. Milestone 29 — Candidate Profile UX v1
4. Milestone 34 — UI v0 (read-only surface)

Interpretation: complete correction-track risk reduction in parallel with early
M25 closeout, then bias execution toward the product feedback loop (`M28` ->
`M29` -> `M34`) rather than new infrastructure plumbing.

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

# ACTIVE ROADMAP — Product Expansion (Milestones 25–34)

These milestones intentionally shift focus from foundational plumbing (largely complete) into:
- provider expansion at scale (with explicit TOS/robots/legal evaluation),
- alerting + multi-user experience,
- resume ingestion and profile UX,
- and an intentionally boring, read-only UI surface.

## Milestone 25 — Provider Availability Always-On (M12 Closeout) ◐

Goal: Provider availability becomes explicit, deterministic product truth on every run.
Status: ◐ Incomplete — artifact exists, but is not guaranteed on all terminal paths.

Definition of Done
- [ ] `provider_availability` artifact emitted on every terminal path:
  - success
  - partial failure
  - early exit
  - zero-provider scenario
- [ ] Zero-provider state explicitly represented (not omitted)
- [ ] Deterministic ordering of providers in artifact
- [ ] Schema validation enforced in CI
- [ ] One forced-failure proof run captured
- [ ] One zero-provider proof run captured

Receipts Required
- Success + failure + zero-provider artifact examples
- CI tests proving artifact presence across all terminal paths
- Proof doc in `docs/proof/`

---

## Milestone 26 — Provider Onboarding Factory v1 (TOS + Robots + Scale) ◐

Goal: Add new career sites/providers safely at scale with a standardized, mostly automated onboarding flow.
Status: ◐ New

Rationale
Provider expansion is the growth engine, but it must remain:
- legally conservative,
- reproducible,
- and operationally boring.

This milestone formalizes a “provider onboarding factory” that:
1) evaluates the site (structure + robots),
2) performs a conservative TOS review and records the decision,
3) builds tests + fixtures,
4) generates config + proofs,
5) and produces a go/no-go receipt bundle.

Definition of Done
- [ ] Provider onboarding “one command” entrypoint exists (offline-first), producing a deterministic receipt bundle:
  - website metadata snapshot (host, canonical job URL patterns, robots status, crawl-delay if present)
  - conservative TOS evaluation record (manual decision captured as structured artifact)
  - scrape_mode decision (`snapshot_only` vs `live_allowed`) recorded
  - rate-limit plan recorded (per-host)
  - user-agent policy recorded
  - opt-out/tombstone plan recorded
- [ ] A versioned schema exists for the onboarding receipt bundle (provider onboarding is auditable)
- [ ] Provider registry tooling supports “pending provider” state until receipts exist
- [ ] CI enforces: live-enabled providers MUST have onboarding receipts + policy block
- [ ] At least 5 new providers onboarded using the factory (proving scale)

Receipts Required
- Versioned onboarding receipt schema + tests
- Proof doc showing an end-to-end onboarding for one provider
- “5 providers added” proof index (links to each receipt bundle)

---

## Milestone 27 — Provider Governance Pack v1 (Policy-Aware Runtime) ◐

Goal: Runtime behavior enforces provider policy decisions (not just docs).
Status: ◐ New

Definition of Done
- [ ] `provider_policy` schema versioned (policy decisions are structured and enforceable)
  - includes: robots_mode, tos_mode, scrape_mode, rate limits, UA string, decision timestamp, decision author
- [ ] Policy decision recorded in provenance for every provider execution
- [ ] Per-host rate limits enforced via config (not ad-hoc sleeps)
- [ ] Provider tombstone lifecycle documented and tested
- [ ] CI enforces policy presence for live-enabled providers
- [ ] At least 3 providers run live under policy-aware runtime with receipts

Receipts Required
- Schema + invariants tests
- Provenance proof showing policy decision fields in a real run
- Proof doc showing rate limit enforcement and tombstone behavior

---

## Milestone 28 — Alerts & Digests v1 (Artifact-First Notifications) ◐

Goal: Users receive daily/weekly digests without UI coupling and without raw JD leakage.
Status: ◐ New

Definition of Done
- [ ] Digest artifact schema versioned (`digest.schema.v1.json`)
- [ ] Deterministic digest generation from UI-safe inputs only
- [ ] Candidate-aware digests supported
- [ ] Configurable cadence (daily/weekly)
- [ ] Alert emission writes a receipt artifact (even when external notify is disabled)
- [ ] “Quiet mode” default (external delivery opt-in)
- [ ] Cost accounting integrated

Receipts Required
- Two-run determinism proof
- Digest artifact example
- Quiet-mode suppression receipt proof

---

## Milestone 29 — Candidate Profile UX v1 (Backend-First Product Loop) ◐

Goal: Validate product workflow with minimal UI dependency: candidate profiles become usable via CLI/API.
Status: ◐ New

Definition of Done
- [ ] Candidate create/list/switch workflow stable (CLI + API)
- [ ] Candidate profile fields versioned (seniority, role archetype, location, skills)
- [ ] Profile hash deterministic and stable
- [ ] `/v1/profile` endpoint added (read/write within contract)
- [ ] `/v1/latest` reflects candidate isolation
- [ ] UI-safe response contract documented
- [ ] Simulated UI proof (curl scripts + example JSON)

Receipts Required
- Isolation test suite passes
- Profile artifact examples (create/update)
- Proof doc validating API contract and stability

---

## Milestone 30 — Resume Ingestion v1 (Bounded, Offline-First) ◐

Goal: Resume ingestion exists without violating SSRF/egress contracts or leaking sensitive content.
Status: ◐ New

Definition of Done
- [ ] Local resume ingestion supported (PDF/text)
- [ ] Resume parsed into structured fields only (no raw resume stored in run artifacts)
- [ ] Resume hash versioned + stable
- [ ] Resume change triggers profile hash update deterministically
- [ ] Network Shield enforced (no remote resume fetch in v1)
- [ ] Resume artifact schema versioned and validated

Receipts Required
- Resume artifact example (structured-only)
- Hash stability proof
- Redaction boundary tests proving no raw content serialized

---

## Milestone 31 — Multi-User Experience v1 (Usable Isolation + Audit) ◐

Goal: Multi-user becomes experiential: multi-candidate workflows are clean, inspectable, and safe.
Status: ◐ New

Definition of Done
- [ ] Per-candidate digests functional
- [ ] Per-candidate alert toggles supported
- [ ] Audit trail includes “actor identity placeholder” even before real auth
- [ ] Cross-user leakage tests expanded
- [ ] CLI + API parity verified
- [ ] Backward compatibility for `local` preserved

Receipts Required
- Multi-candidate run proof bundle
- Audit trail examples
- Isolation/leakage test receipts

---

## Milestone 32 — Auth Scaffold v1 (Shape Without Cathedral) ◐

Goal: Prepare for authentication and authorization without prematurely building RBAC complexity.
Status: ◐ New

Definition of Done
- [ ] Authentication middleware seam exists
- [ ] “Anonymous/dev mode” explicitly defined
- [ ] Actor identity injected into audit artifacts
- [ ] Auth contract documented (what is promised now vs later)
- [ ] No UI required

Receipts Required
- Audit artifact showing identity fields
- Middleware tests
- Proof doc documenting boundaries and non-goals

---

## Milestone 33 — Provider Maintenance Tooling v1 (Operate at Scale) ◐

Goal: Provider lifecycle is inspectable and manageable as provider count grows.
Status: ◐ New

Definition of Done
- [ ] Provider health trend artifact exists (availability + failure reasons over time)
- [ ] Disable/tombstone CLI workflow hardened (safe, receipted)
- [ ] Rate-limit breach detection artifact exists
- [ ] Provider error-rate summary available via API
- [ ] CI test simulating provider degradation and verifying artifacts

Receipts Required
- Health trend artifact example
- Degradation simulation proof
- Tombstone workflow proof

---

## Milestone 34 — UI v0 (Boring, Read-Only Product Surface) ◐

Goal: Minimal UI to validate product loop while keeping backend boring and authoritative.
Status: ◐ New

Definition of Done
- [ ] Read-only dashboard exists (no mutations)
- [ ] Latest run view
- [ ] Top jobs view
- [ ] Explanation artifact view
- [ ] Provider availability + run health surfaced
- [ ] UI consumes only documented API endpoints
- [ ] “No raw JD leakage” enforced by contract tests

Receipts Required
- Screenshot proof
- API contract validation proof
- No raw JD leakage proof

---

# PARKED — Hardware-Gated On-Prem Track (Deferred)

These milestones are intentionally parked until on-prem hardware timing and operational bandwidth align.
Do not burn engineering cycles here until the Pi cluster / on-prem environment is ready for sustained runs.

## Milestone 40 — On-Prem Migration Contract (AWS → k3s) ◐

Goal: Migration is engineered, not improvised.
Status: ◐ On-prem deploy runbooks + deterministic rehearsal are in place, and the dual-run diff contract tool/receipt are landed; milestone remains incomplete until a real AWS-vs-onprem run pair is executed and receipted.
Evidence: `ops/onprem/RUNBOOK_DEPLOY.md`, `ops/onprem/RUNBOOK_DNS.md`, `scripts/onprem_rehearsal.py`, `schemas/onprem_rehearsal_receipt.schema.v1.json`, `scripts/compare_run_artifacts.py`, `tests/test_compare_run_artifacts.py`, `docs/proof/m20-dual-run-diff-2026-02-17.md`.

Definition of Done
- [ ] Data migration plan documented
- [ ] Artifact compatibility verified
- [ ] Backwards compatibility test suite passes
- [x] Rollback plan documented
- [ ] Dual-run validation (AWS vs on-prem output diff) executed with a real run pair (tooling/contract is landed)
- [ ] Zero artifact schema changes required
- [ ] Migration dry run executed

Receipts Required
- Side-by-side artifact diff proof
- Migration dry run log
- Rollback rehearsal doc

---

## Milestone 41 — On-Prem Stability Proof (Post-Migration) ⏸

Goal: On-prem becomes primary without chaos.
Status: ⏸ Harness merged; awaiting 72h execution receipt on on-prem cluster.
Evidence: `ops/onprem/RUNBOOK_BORING_72H_PROOF.md`, `docs/proof/onprem-ops-hardening-2026-02-13.md`, `docs/proof/m21-harness-implementation-2026-02-21.md`, `docs/proof/m21-72h-onprem-proof-template-2026-02-21.md`, `docs/proof/m21-72h-onprem-proof-executed-YYYY-MM-DD.md`.

Definition of Done
- [x] 72h harness + proof template merged and runnable (`make m21-stability-harness`)
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

# ARCHIVE — Milestones 1–24 (Completed / Superseded / Historical)

**Archive rule:** These milestones are “done enough” for their phase.
Do not reopen unless a regression threatens determinism, replayability, deployability, or legal safety.

> NOTE: The archive retains full milestone text for historical continuity, receipts, and auditability.
> Active work must happen only in the “ACTIVE ROADMAP” section above.

---

## Milestone 24 — Multi-User Plumbing v1 (Foundation + Isolation) ✅

Goal: Prepare for product without UI complexity.
Status: ✅ Candidate registry/schema/isolation are implemented with backward compatibility for `local`, and run audit trail artifacts now emit on every finalized run path.
Evidence: `schemas/candidate_profile.schema.v1.json`, `schemas/run_audit.schema.v1.json`, `src/ji_engine/candidates/registry.py`, `src/ji_engine/pipeline/runner.py`, `scripts/candidates.py`, `tests/test_candidate_namespace.py`, `tests/test_candidate_state_contract.py`, `tests/test_run_health_artifact.py`, `docs/proof/m24-audit-trail-artifact-v1-2026-02-18.md`.

Definition of Done
- [x] `candidate_profile.schema.json` defined
- [x] candidate registry exists (CRUD via file/CLI only; no web UI required)
- [x] Candidate isolation enforced end-to-end (paths, pointers, index)
- [x] Cross-user leakage tests implemented
- [x] Audit trail artifacts exist (who/what triggered run; profile hash change record)
- [x] Backward compatibility maintained for `local`
- [x] No authentication/UI implemented yet

Receipts Required
- Isolation test suite
- Audit trail proof artifacts
- Backward compat proof

---

## Milestone 23 — Code Surface & Bloat Review (Entropy Reduction) ✅

Goal: Eliminate entropy before adding product surfaces.
Status: ✅ Focused cleanup, runner seam extraction, dead-code/dependency removals, and explicit public API boundary guardrails are landed.
Evidence: `docs/proof/m23-entropy-reduction-pr1-2026-02-18.md`, `docs/proof/m23-entropy-reduction-pr2-2026-02-18.md`, `docs/proof/m23-entropy-reduction-pr4-2026-02-19.md`, `docs/proof/m23-entropy-reduction-pr5-deps-2026-02-19.md`, `docs/proof/m23-runner-seam-extraction-pr1-2026-02-18.md`, `docs/proof/m23-runner-seam-extraction-pr2-2026-02-19.md`, `docs/PUBLIC_API_BOUNDARIES.md`, `tests/test_public_api_boundaries.py`, `docs/proof/m23-public-api-boundaries-2026-02-19.md`.

Definition of Done
- [x] Dead code removed
- [x] Unused deps removed
- [x] Duplicate logic consolidated
- [x] File structure rationalized
- [x] Public API boundaries clarified
- [x] Complexity hotspots documented
- [x] Size diff documented

Receipts Required
- Before/after LOC diff
- Dependency tree comparison
- Simplification proof doc

---

## Milestone 22 — Security Review Pack v1 (Audited Posture) ✅

Goal: Security posture is audited, not assumed.
Status: ✅ Formal threat model, dependency audit receipt, IAM checklist, redaction-behavior tests, and CI dependency-audit guardrail are landed; follow-on hardening for runner redaction default mode is tracked in issue #167.
Evidence: `docs/security/threat_model_v1.md`, `docs/proof/security-dependency-audit-2026-02-17.md`, `docs/proof/m22-redaction-mode-contract-2026-02-18.md`, `SECURITY.md`, `scripts/security_dependency_check.py`, `.github/workflows/ci.yml`, `tests/test_runner_redaction_enforcement.py`, `tests/test_redaction_guard.py`, `tests/test_run_summary_artifact.py`, `docs/LEGAL_POSITIONING.md`.

Definition of Done
- [x] Threat model document created (multi-tenant aware)
- [x] Attack surface review performed
- [x] Secrets handling reviewed + redaction tests enforced
  - Clarification: regex redaction is best-effort only, and is not the primary security control
  - Primary control: no secrets are written to artifacts/log bundles by construction
- [x] Dependency audit completed
- [x] Least-privilege IAM documented (AWS + on-prem)
- [x] Static analysis tool integrated
- [x] SECURITY.md aligned with reality
- [x] “User-supplied URL/provider” policy documented (SSRF/egress stance)
  - Follow-on hardening tracked in `https://github.com/penquinspecz/SignalCraft/issues/167`

Receipts Required
- Threat model artifact
- Dependency audit report
- IAM review checklist
- Tests proving secrets are never serialized into run artifacts/log bundles

---

## Milestone 21 — On-Prem Stability Proof (Post-Migration) ⏸
(Archived historical entry; active copy lives in “PARKED” section as Milestone 41.)

---

## Milestone 20 — On-Prem Migration Contract (AWS → k3s) ◐
(Archived historical entry; active copy lives in “PARKED” section as Milestone 40.)

---

## Milestone 19C — Promote Semantics & Failback v1 (Batch-First, Endpoint-Ready) ✅

Goal: “Promote” and “failback” are explicit, deterministic operations rather than tribal knowledge.
Status: ✅ Semantics are documented and deterministic failback rehearsal receipts are captured (dry-run + apply) with no pointer drift and no artifact loss in the tested run.
Evidence: `docs/dr_orchestrator.md`, `docs/dr_promote_failback.md`, `scripts/ops/dr_drill.sh`, `scripts/ops/dr_failback_pointers.sh`, `scripts/verify_published_s3.py`, `scripts/compare_run_artifacts.py`, `docs/proof/m19c-failback-pointers-dry-run-2026-02-22.md`, `docs/proof/m19c-failback-rehearsal-20260227T052811Z.md`.

Definition of Done
- [x] Batch-mode promote semantics documented (what changes today, and what does not)
- [x] Future UI/API promote semantics documented (DNS/endpoint cutover contract)
- [x] Failback safety contract documented (freeze, verify, reconcile, switchback, monitor)
- [x] Deterministic promote decision path exists in DR drill (`--auto-promote=true` + explicit bypass gate)
- [x] DR Determinism Audit Complete (`scripts/audit_determinism.sh` passes; no committed local state/cache artifacts; DR guardrails enforced)
- [x] DR Docs Coherence Gate: PASS (Definition: a new operator can run a drill from docs only, including trigger semantics, digest image selection, control-plane continuity, and promotion/failback commands.)
- [x] Cost guardrails: PASS (default iteration is bringup-only once + restore-only + validate-only; full drill requires explicit `--allow-full-drill` and receipts)
- [x] Deterministic failback command path exists (dry-run + apply)
- [x] Rehearsed failback proves no pointer drift and no artifact loss

Receipts Required
- Promote decision receipt with operator identity + ticket reference
- Pointer/state verification receipts pre/post promote and pre/post failback
- Artifact diff receipt proving deterministic reconciliation before switchback
- Cost receipts for drill runs (`drill.cost.inputs.json`, `drill.cost.actual.json`, `drill.phase_timestamps.json`)

---

## Milestone 19B — DR Orchestration v1 (Auto-Detect -> Auto-Validate -> Manual Promote) ✅

Goal: DR detection and Kubernetes DR validation run unattended in AWS, with human-controlled promotion.
Status: ✅ Failure-path and success-path rehearsals are proven and receipted in-repo; success-path reaches `RequestManualApproval` (manual gate) with promote intentionally not executed in this rehearsal.
Evidence: `ops/dr/orchestrator/main.tf`, `ops/dr/orchestrator/lambda/dr_orchestrator.py`, `docs/dr_orchestrator.md`, `ops/dr/orchestrator/README.md`, `scripts/ops/dr_drill.sh`, `Makefile`. Failure-path rehearsal: `docs/proof/m19b-orchestrator-failure-20260222T214946Z.md`. Success-path manual-gate proof: `docs/proof/m19b-successpath-reaches-manual-approval-20260227T050707Z.md`. Iterative unblock log: `docs/proof/m19b-successpath-iam-unblock-log-2026-02-27.md`.

Definition of Done
- [x] Batch-first health signals emitted: pipeline freshness and publish correctness
- [x] CloudWatch alarms exist for freshness breach and publish correctness failure
- [x] Step Functions flow executes: `check_health -> bringup -> restore -> validate -> notify`
- [x] Validation proves DR runner Kubernetes control plane health before any promotion decision
- [x] Manual approval gate is mandatory before promote
- [x] Auto-promote is explicitly disabled
- [x] Every orchestration phase writes a receipt object to S3
- [x] Deterministic non-production drill command exists for bringup -> restore -> validate -> optional promote -> teardown
- [x] Control Plane Bundle continuity implemented (`publish_bundle.sh`, `fetch_bundle.sh`, `apply_bundle_k8s.sh`)
- [x] DR restore applies same control-plane bundle as primary before validation
- [x] Restore receipts include `bundle_uri`, `bundle_sha256`, and applied config counts
- [x] At least one full success-path rehearsal receipt bundle captured
- [x] At least one failure-path rehearsal receipt bundle captured

Receipts Required
- Step Functions execution history export
- S3 phase receipts (`check_health`, `bringup`, `restore`, `validate`, `notify`, `request_manual_approval`, `record_manual_decision`)
- Alarm transition proof (`OK -> ALARM -> OK`)

---

## Milestone 19A — Release Integrity for DR Deployments ✅

Goal: Every DR deploy uses deterministic, architecture-safe release units.
Status: ✅ Multi-arch build/publish, digest-pinned release metadata, CI evidence, and DR image validation receipts are landed and proven for release discipline.
Evidence: `scripts/release/build_and_push_ecr.sh`, `scripts/release/write_release_metadata.py`, `scripts/release/verify_ecr_image_arch.py`, `scripts/release/check_release_proof_bundle.py`, `.github/workflows/release-ecr.yml`, `scripts/ops/dr_validate.sh`, `scripts/ops/assert_image_ref_digest.py`, `ops/aws/EKS_ECR_GOLDEN_PATH.md`, `docs/proof/m19a-digest-pinning-release-proof-2026-02-22.md`.

Definition of Done
- [x] ECR image publish is multi-arch per commit SHA (`linux/amd64` + `linux/arm64`) under one tag
- [x] Release metadata persisted with `git_sha`, `image_repo`, `image_tag`, `image_digest`, build timestamp, and supported architectures
- [x] DR validate path accepts `IMAGE_REF` as digest (preferred) or tag (dev fallback)
- [x] CI gate fails when required architecture (`arm64`) is missing
- [x] CI gate fails when DR image precheck cannot validate arm64 compatibility
- [x] Non-dev deployment paths default to digest pinning (tag opt-in for development only)
- [x] Release proof bundle always includes metadata artifact + CI gate evidence

Receipts Required
- Release metadata artifact (`release-<sha>.json`)
- CI receipt showing multi-arch manifest verification
- DR validate receipt showing digest-pinned `IMAGE_REF`

---

## Milestone 18 — Release Discipline v1 (Releases Are Proof Events) ✅

Goal: Releases are evidence-backed.
Status: ✅ Release process and proof artifacts exist, changelog enforcement is CI-enforced for release-intent PRs, and reproducible build verification is now receipt-backed.
Evidence: `docs/RELEASE_PROCESS.md`, `docs/proof/release-v0.1.0.md`, `docs/proof/m18-reproducible-build-verification-2026-02-21.md`, `scripts/preflight_env.py`, `scripts/check_changelog_policy.py`, `tests/test_check_changelog_policy.py`, `tests/fixtures/github_event_pull_request_release.json`, `tests/fixtures/github_event_pull_request_nonrelease.json`, `Makefile` targets `changelog-policy` and `release-policy`, `.github/workflows/ci.yml`.

Definition of Done
- [x] Release checklist codified
- [x] Preflight validation script exists
- [x] Changelog enforcement policy
- [x] Every release includes proof bundle
- [x] Reproducible build instructions verified

Receipts Required
- One full release dry-run proof bundle

---

## Milestone 17 — Dashboard Plumbing v2 (Backend-First UI Readiness) ✅

Goal: Backend is UI-ready without becoming UI-first.
Status: ✅ `/version`, candidate-aware latest endpoint, artifact index endpoint, API docs, optional dependency isolation, and bounded fail-closed reads are landed.
Evidence: `src/ji_engine/dashboard/app.py`, `src/ji_engine/artifacts/catalog.py`, `src/ji_engine/pipeline/artifact_paths.py`, `tests/test_dashboard_app.py`, `tests/test_artifact_contract_registry.py`, `tests/test_make_dashboard_missing_extras.py`, `scripts/dashboard_offline_sanity.py`, `Makefile` targets `dashboard` and `dashboard-sanity`, `docs/DASHBOARD.md`, `docs/DASHBOARD_API.md`, `docs/OPERATIONS.md`, `scripts/dev/curl_dashboard_proof.sh`, `docs/proof/m17-api-boring-pack-2026-02-15.md`, `docs/proof/m17-artifact-index-endpoint-2026-02-14.md`, `docs/proof/m17-api-boring-pack-smoke-negative-2026-02-15.md`, `docs/proof/p1-artifact-download-size-cap-2026-02-17.md`, `docs/proof/dashboard-offline-sanity-m14-m15-m16-2026-02-21.md`, `docs/proof/artifact-contract-consistency-2026-02-21.md`, `docs/proof/m17-dashboard-modes-and-preflight-2026-02-21.md`, `docs/proof/m17-artifact-ui-safety-contract-tightening-2026-02-21.md`.

Definition of Done
- [x] `/version` endpoint
- [x] `/runs/latest` endpoint is candidate-aware (implemented as `/v1/latest?candidate_id=...`)
- [x] Artifact index endpoint(s) are stable and documented
- [x] API contract documented
- [x] Optional deps isolated cleanly
- [x] Read-time validation is fail-closed and bounded

Receipts Required
- API proof doc
- Simulated UI proof (curl scripts + sample payloads)

---

## Milestone 16 — Explainability v1 (Make Scores Interpretable) ✅

Goal: Scores are explainable and stable.
Status: ✅ `explanation_v1` schema + artifact contract is landed with deterministic ordering, bounded surfaced signal/penalty contributions, UI-safe catalog enforcement, and receipt coverage.
Evidence: `schemas/explanation.schema.v1.json`, `src/ji_engine/pipeline/runner.py`, `src/ji_engine/pipeline/artifact_paths.py`, `src/ji_engine/artifacts/catalog.py`, `src/ji_engine/dashboard/app.py`, `tests/test_explanation_artifact_v1.py`, `docs/proof/m16-explanation-artifact-v1-2026-02-19.md`.

Definition of Done
- [x] `explanation_v1` structure implemented
- [x] Top contributing signals surfaced
- [x] Penalties visible
- [x] Semantic contribution bounded + surfaced (if used)
- [x] Deterministic ordering enforced

Receipts Required
- Artifact snapshot proof
- Ordering tests

---

## Milestone 15 — AI Per-Job Briefs v1 (Coaching Per Job, Deterministic Cache) ✅

Goal: Profile-aware coaching per job.
Status: ✅ Job brief schema v1 is enforced with fail-closed behavior, deterministic cache keys are preserved, and CI tests validate valid/invalid paths.
Evidence: `schemas/ai_job_brief.schema.v1.json`, `src/jobintel/ai_job_briefs.py`, `tests/test_ai_job_briefs.py`, `tests/test_ai_job_briefs_schema.py`, `docs/proof/m15-job-brief-schema-enforcement-2026-02-19.md`.

Definition of Done
- [x] Candidate profile hash contract defined
- [x] `ai_job_brief.schema.v1.json` enforced
- [x] Cache keyed by job_hash + profile_hash + prompt_version
- [x] Cost accounting integrated
- [x] Deterministic hash stability verified
- [x] Schema validation enforced in CI

Receipts Required
- Deterministic diff proof
- Cost artifact proof

---

## Milestone 14 — AI Insights v1 (Grounded Intelligence, Bounded) ✅

Goal: Weekly insights are useful and bounded.
Status: ✅ Input/output schemas, deterministic 7/14/30 trend aggregation, structured-only skill token extraction, strict fail-closed output validation, and deterministic Top 5 actions are landed.
Evidence: `schemas/ai_insights_input.schema.v1.json`, `schemas/ai_insights_output.schema.v1.json`, `src/ji_engine/ai/insights_input.py`, `src/jobintel/ai_insights.py`, `tests/test_ai_insights.py`, `tests/test_insights_input.py`, `tests/test_ai_insights_schema_enforcement.py`, `tests/test_ai_insights_trends.py`, `docs/prompts/weekly_insights_v4.md`, `docs/proof/m14-ai-insights-schemas-trends-2026-02-19.md`.

Definition of Done
- [x] Deterministic input schema versioned
- [x] 7/14/30 day trend analysis
- [x] Skill token extraction from structured fields (not raw JD)
- [x] Strict output schema enforcement
- [x] Cache keyed by input hash + prompt version
- [x] “Top 5 Actions” section included
- [x] No raw JD leakage

Receipts Required
- Two-run determinism proof
- Schema validation tests

---

## Milestone 13 — Run Indexing v1 (Metadata Without Rewrites) ✅

Goal: Remove “filesystem-as-database” pain without abandoning artifacts.

Rationale: Artifacts stay as blobs. Indexing is metadata only.
Status: ✅ SQLite index, deterministic rebuild, repository-only run resolution, and SQLite-backed read-path migration are landed.
Evidence: `src/ji_engine/state/run_index.py`, `src/ji_engine/run_repository.py`, `scripts/rebuild_run_index.py`, `scripts/report_changes.py`, `docs/proof/m13-run-indexing-v1-2026-02-13.md`, `docs/proof/m13-no-run-filesystem-scan-outside-tests-2026-02-15.md`, `docs/proof/m13-readpath-history-sqlite-2026-02-15.md`, `tests/test_m13_no_run_filesystem_scan_repo_wide.py`, `tests/test_run_repository.py`, `tests/test_report_changes.py`.

Definition of Done
- [x] RunRepository seam is the only way to resolve runs (no scattered path-walking)
- [x] A minimal index exists for O(1) “latest run” + recent run listing:
  - Option A (preferred on-prem friendly): SQLite index in state (single-writer safe)
  - Option B (cloud friendly): DynamoDB / Postgres later (not required now)
- [x] Index is append-only and derived from artifacts (rebuildable)
- [x] Dashboard endpoints do not require directory scans for the common case
- [x] Index rebuild tool exists (deterministic)
- [x] At least one real read path (`history`, `diff`, or `retention`) is migrated to SQLite-backed lookup instead of walking JSON files

Receipts Required
- Index rebuild proof
- Determinism proof: index rebuild yields identical results
- Dashboard performance sanity proof (basic benchmark notes)
- Read-path migration proof showing SQLite-backed resolution for at least one of: history/diff/retention

---

## Milestone 12 — Operations Hardening Pack v1 (Explicit Failure + Inspectability) ◐

Goal: Failure is explicit and inspectable.
Status: ◐ Run health taxonomy + summary + run inspection + failure playbook receipts are landed; strict “provider availability artifact generated every run” is still open.
Evidence: `schemas/run_health.schema.v1.json`, `schemas/run_summary.schema.v1.json`, `schemas/provider_availability.schema.v1.json`, `docs/OPS_RUNBOOK.md`, `docs/proof/m12-provider-availability-artifact-2026-02-15.md`, `docs/proof/m12-failure-playbook-receipts-2026-02-14.md`, `scripts/run_daily.py`, `tests/test_run_health_artifact.py`.

Definition of Done
- [x] `failed_stage` always populated on failure
- [x] Cost telemetry always written (even on partial failure)
- [ ] Provider availability artifact generated every run
- [x] One-command run inspection tooling (human-friendly)
- [x] CI smoke matches real run structure
- [x] Failure playbook updated
- [x] **Candidate namespace is treated as first-class (default `local`)**:
  - candidate_id flows through orchestration
  - artifacts + pointers do not collide across candidates
  - backward compatibility policy documented

Receipts Required
- Forced failure proof run (with artifacts)
- Artifact inspection proof
- Candidate isolation proof artifacts/tests

---

## Milestone 11 — Artifact Model v2 (Legal + UI-Safe by Design) ✅

Goal: Legality + replayability enforced by shape.
Status: ✅ UI-safe/replay-safe schema contracts and API boundary enforcement are landed.
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

## Milestone 10 — Provider Platform v1 (Boring Expansion) ✅

Goal: Provider expansion becomes boring and safe.
Status: ✅ Registry schema/guardrails, Network Shield requirements, registry-hash provenance, and tombstone semantics are landed.
Evidence: `schemas/providers.schema.v1.json`, `docs/proof/m10-provider-registry-hash-2026-02-15.md`, `docs/proof/m10-provider-tombstone-2026-02-15.md`, `src/ji_engine/providers/registry.py`, `src/ji_engine/utils/network_shield.py`, `tests/test_provider_registry.py`, `tests/test_network_shield.py`.

Definition of Done
- [x] Versioned provider registry schema exists
- [x] **Network Shield v1 (SSRF/Egress hardening) is required before any provider may set `live_enabled=true`**, including:
  - denylist coverage for `localhost`/`127.0.0.1`, RFC1918 ranges, and link-local metadata endpoints (for example `169.254.169.254`)
  - redirect revalidation on every hop
  - max-bytes streamed download cap enforcement
- [x] Registry hash recorded in provenance
- [x] Provider config validated in CI (schema + invariants)
- [x] Snapshot fixtures enforced per provider (enabled snapshot providers)
- [x] Provider tombstone supported (opt-out / takedown path)
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

## Archive — Milestones 1–9 (Completed / Superseded)

This archive is retained for historical continuity; the active roadmap above remains canonical.

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
**Status:** Offline multi-provider proof exists; “fully config-driven provider registry” still needs consolidation/hardening as a single coherent milestone (see Milestone 10 above).
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
