# Architecture

SignalCraft is architected as a deterministic career intelligence product, not a one-off scraping script. The system is designed so runs are reproducible, explainable, and operationally inspectable.

Primary pipeline entrypoint: `scripts/run_daily.py`

## Product-Grade Architecture Overview

### Layered system

1. Ingestion layer (config-driven providers)
- Provider registry drives provider behavior and validation.
- Snapshot and live modes are policy-aware and provenance-backed.
- Provider contracts are enforced fail-closed.

2. Deterministic normalization
- Inputs are normalized into stable structures for downstream stages.
- Semantic normalization (`semantic_norm_v1`) and other canonical transforms are versioned for replay safety.
- Stable sorting and canonical field ordering are enforced where outputs are compared.

3. Identity engine
- Jobs receive stable identity signals to track continuity across runs.
- Identity supports dedupe, run-over-run comparison, and deterministic tie-breaking.

4. Scoring engine
- Base scoring is deterministic and explainable.
- Semantic influence (when enabled) is bounded and policy-controlled.
- Score outputs remain replayable from recorded artifacts.

5. History and diff engine
- Per-run artifacts are written under `state/runs/<run_id>/`.
- Diff logic captures new/changed/removed items using stable identity and fingerprints.
- Run report + provenance provide post-run forensic detail.

6. AI insights sidecar
- AI reads deterministic artifacts; it is not a source-of-truth subsystem.
- Inputs are structured and cache-keyed for reproducibility.
- Fail-closed behavior preserves deterministic core outputs.

7. Delivery layer (API + object store)
- Dashboard/API surfaces run artifacts for operational inspection.
- Object-store publishing supports latest pointers and run-scoped retrieval.
- Delivery does not replace source employer pages; it delivers intelligence and links.

### Runtime topology (ASCII)

```text
[Provider Registry + Policy]
            |
            v
  [Ingestion: Snapshot/Live]
            |
            v
 [Deterministic Normalization]
            |
            v
      [Identity Engine]
            |
            v
      [Scoring Engine] -----> [History + Diff Engine]
            |                           |
            |                           v
            |                    [Run Artifacts]
            |                           |
            +-------------> [AI Insights Sidecar]
                                        |
                                        v
                              [Delivery: API + Object Store]
```

## AI Philosophy

AI is a last-mile intelligence layer, never the source of truth.

- Deterministic core first: ingestion, normalization, identity, scoring, and diffs are artifact-grounded.
- Guardrailed execution: AI outputs are cache-backed, schema-validated, and fail-closed.
- Reproducible settings: deterministic model/config controls (including deterministic temperature policy where configured).
- Bounded influence: AI/semantic paths cannot unilaterally rewrite base ranking without explicit bounded controls.
- Explainability preserved: score evidence and reasoning fields remain inspectable even when AI layers are enabled.

## Multi-User Future Design

SignalCraft currently prioritizes deterministic single-operator reliability, with multi-user architecture planned as additive isolation.

### Candidate isolation model
- Candidate identity becomes a first-class key (`candidate_id`) for run scoping and state separation.
- User-level state overlays remain isolated per candidate/profile domain.

### Profile ingestion
- Candidate profiles become schema-versioned inputs with deterministic validation.
- Profile changes are hash-tracked to support cache invalidation and reproducible re-runs.

### Resume normalization pipeline
- Resume/profile ingestion normalizes raw input into canonical structured fields.
- Canonicalization is versioned so behavior changes are explicit and testable.

### Per-user artifact partitioning
- Artifacts partition by candidate/profile to prevent cross-user leakage.
- UI-safe and replay-safe artifacts follow explicit contract boundaries.

### S3 path isolation model
- Object-store keys evolve toward namespaced paths, for example:
  - `<prefix>/candidates/<candidate_id>/runs/<run_id>/...`
- Compatibility layers can preserve existing single-user paths during migration.

## Legal-Aware Design

SignalCraft is designed as a discovery-and-alert net, not a replacement destination.

- Original URLs preserved: canonical source links are retained in artifacts and outputs.
- Attribution preserved: source/provider provenance is recorded alongside artifacts.
- No content transformation beyond extraction: the system extracts structured intelligence signals; it does not position transformed content as the source-of-record.
- Clear discovery-only intent: users are expected to verify details and apply on the original employer site.

See `docs/LEGALITY_AND_ETHICS.md` for operational guardrails and policy posture.

## Related Contracts

- `docs/OPERATIONS.md`
- `docs/RUN_REPORT.md`
- `docs/CI_SMOKE_GATE.md`
- `docs/ROADMAP.md`
