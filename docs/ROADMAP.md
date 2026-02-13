© 2026 Chris Menendez. Source Available — All Rights Reserved.  
See LICENSE for permitted use.

# SignalCraft Roadmap

This roadmap is the anti-chaos anchor.  
We optimize for:

1) Deterministic outputs  
2) Debuggability  
3) Deployability  
4) Incremental intelligence  
5) Productization without chaos  
6) Infrastructure portability  

If a change doesn’t advance a milestone’s Definition of Done (DoD), it’s churn.

---

# Document Contract

This file is the plan. The repo is the truth.

Every merged PR must:
- Declare which milestone moved
- Include evidence paths (tests, logs, proof bundles)
- Keep “Current State” aligned with actual behavior

---

# Non-Negotiable Guardrails

- One canonical pipeline entrypoint (`scripts/run_daily.py`)
- Determinism > cleverness
- Explicit input selection reasoning
- Small, test-backed changes
- Operational truth lives in artifacts
- AI is last-mile only
- No credentialed scraping
- Legal constraints enforced in design
- CI must prove determinism offline
- Cloud runs must be replayable locally
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

---

# Current State

Last verified: 2026-02-13T01:00:59Z @ 555b095292109864c3016a52084e78e6616bd9d6  
Latest release: v0.1.0

Foundation exists:
- Deterministic scoring
- Replayability
- Snapshot-backed providers
- AI weekly insights (guardrailed)
- Per-job briefs
- Cost guardrails
- Discord alerts
- Minimal dashboard API
- CI smoke enforcement

Phase 1 is real.

---

# NEW ROADMAP — Thick Milestones

---

## Milestone 10 — Provider Platform v1

Goal: Provider expansion becomes boring.

Definition of Done

- [ ] Versioned provider registry schema exists
- [ ] Registry hash recorded in provenance
- [ ] Provider config validated in CI
- [ ] Snapshot fixtures enforced per provider
- [ ] Provider tombstone supported
- [ ] At least 3 new providers added via registry only
- [ ] No core pipeline modification required to add provider

Receipts Required

- Deterministic ordering tests
- Snapshot completeness enforcement
- Proof doc in docs/proof/

---

## Milestone 11 — Artifact Model v2

Goal: Legality + replayability enforced by shape.

Definition of Done

- [ ] UI-safe artifact schema versioned
- [ ] Replay-safe artifact schema versioned
- [ ] UI-safe artifacts contain no raw JD text
- [ ] Redaction boundaries enforced by tests
- [ ] Retention policy documented
- [ ] Artifact backward compatibility defined

Receipts Required

- Schema validation suite
- Artifact redaction tests
- Proof doc

---

## Milestone 12 — Operations Hardening Pack

Goal: Failure is explicit and inspectable.

Definition of Done

- [ ] failed_stage always populated
- [ ] Cost telemetry always written
- [ ] Provider availability artifact generated
- [ ] One-command run inspection tooling
- [ ] CI smoke matches real run structure
- [ ] Failure playbook updated

Receipts Required

- Forced failure proof run
- Artifact inspection proof

---

## Milestone 13 — AI Insights v1 (Grounded Intelligence)

Goal: Weekly insights are useful and bounded.

Definition of Done

- [ ] Deterministic input schema versioned
- [ ] 7/14/30 day trend analysis
- [ ] Skill token extraction from structured fields
- [ ] Strict output schema enforcement
- [ ] Cache keyed by input hash + prompt version
- [ ] “Top 5 Actions” section included
- [ ] No raw JD leakage

Receipts Required

- Two-run determinism proof
- Schema validation tests

---

## Milestone 14 — AI Per-Job Briefs v1

Goal: Profile-aware coaching per job.

Definition of Done

- [ ] Candidate profile hash contract defined
- [ ] ai_job_brief.schema.json enforced
- [ ] Cache keyed by job_hash + profile_hash
- [ ] Cost accounting integrated
- [ ] Deterministic hash stability verified
- [ ] Schema validation enforced in CI

Receipts Required

- Deterministic diff proof
- Cost artifact proof

---

## Milestone 15 — Explainability v1

Goal: Scores are interpretable.

Definition of Done

- [ ] explanation_v1 structure implemented
- [ ] Top contributing signals surfaced
- [ ] Penalties visible
- [ ] Semantic contribution bounded + surfaced
- [ ] Deterministic ordering enforced

Receipts Required

- Artifact snapshot proof
- Ordering tests

---

## Milestone 16 — Dashboard Plumbing v2

Goal: Backend-first UI readiness.

Definition of Done

- [ ] /version endpoint
- [ ] /runs/latest endpoint
- [ ] Artifact index endpoint
- [ ] API contract documented
- [ ] Optional deps isolated cleanly

Receipts Required

- API proof doc
- Simulated UI proof

---

## Milestone 17 — Release Discipline v1

Goal: Releases are proof events.

Definition of Done

- [ ] Release checklist codified
- [ ] Preflight validation script exists
- [ ] Changelog enforcement policy
- [ ] Every release includes proof bundle
- [ ] Reproducible build instructions verified

---

# INFRASTRUCTURE EVOLUTION

---

## Milestone 18 — AWS DR & Failover Hardening

Goal: Cloud execution survives failure.

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

## Milestone 19 — AWS → On-Prem Migration Contract

Goal: Migration is engineered, not improvised.

Definition of Done

- [ ] Data migration plan documented
- [ ] Artifact compatibility verified
- [ ] Backwards compatibility test suite passes
- [ ] Rollback plan documented
- [ ] Dual-run validation (AWS vs on-prem output diff)
- [ ] Zero artifact schema changes required
- [ ] Migration dry run executed

Receipts Required

- Side-by-side artifact diff proof
- Migration dry run log
- Rollback rehearsal doc

---

## Milestone 20 — On-Prem Stability Proof (Post-Migration)

Goal: On-prem becomes primary without chaos.

Definition of Done

- [ ] 72-hour continuous k3s run
- [ ] CronJob stability verified
- [ ] Storage durability verified
- [ ] Backup + restore rehearsal on-prem
- [ ] Resource utilization captured
- [ ] Determinism validated against AWS baseline

Receipts Required

- Stability logs
- Restore proof
- Deterministic diff proof

---

# GOVERNANCE & HYGIENE

---

## Milestone 21 — Security Review Pack v1

Goal: Security posture is audited, not assumed.

Definition of Done

- [ ] Threat model document created
- [ ] Attack surface review performed
- [ ] Secrets handling reviewed
- [ ] Dependency audit completed
- [ ] Least-privilege IAM documented
- [ ] Static analysis tool integrated
- [ ] Security.md aligned with reality

Receipts Required

- Threat model artifact
- Dependency audit report
- IAM review checklist

---

## Milestone 22 — Code Surface & Bloat Review

Goal: Eliminate entropy.

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

## Milestone 23 — Multi-User Plumbing (Foundation Only)

Goal: Prepare for product without UI.

Definition of Done

- [ ] candidate_profile.schema.json defined
- [ ] candidate_id integrated in registry
- [ ] Artifact path namespaced by candidate
- [ ] Cross-user leakage tests implemented
- [ ] Backward compatibility maintained
- [ ] No UI implemented

Receipts Required

- Isolation test suite
- Artifact namespace proof

---

# Phase 3 Preview (24–30)

- Authentication + authz
- Resume ingestion
- AI coaching expansion
- AI outreach generation
- Advanced analytics
- Provider scaling
- Cost optimization
- Architecture pruning
- Partnership-ready ingestion
- Production UI

---

# Milestone Philosophy

Fewer, thicker milestones.

Every milestone must:
- Produce artifacts
- Produce tests
- Produce receipts
- Reduce chaos
- Increase product clarity
- Increase infrastructure resilience
