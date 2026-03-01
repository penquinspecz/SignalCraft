© 2026 Chris Menendez. Source Available — All Rights Reserved.
This repository is publicly viewable but not open source.
See [LICENSE](LICENSE) for permitted use.

<p align="center">
  <img alt="SignalCraft" src="assets/brand/signalcraft-wordmark.light.png?raw=1#gh-light-mode-only" width="520">
  <img alt="SignalCraft" src="assets/brand/signalcraft-wordmark.dark.png?raw=1#gh-dark-mode-only" width="520">
</p>

<p align="center">
  <img alt="SignalCraft logo" src="assets/brand/signalcraft-logo.light.png?raw=1#gh-light-mode-only" width="96">
  <img alt="SignalCraft logo" src="assets/brand/signalcraft-logo.dark.png?raw=1#gh-dark-mode-only" width="96">
</p>

# SignalCraft

[![ci](https://github.com/penquinspecz/SignalCraft/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/penquinspecz/SignalCraft/actions/workflows/ci.yml) [![Docker Smoke](https://github.com/penquinspecz/SignalCraft/actions/workflows/docker-smoke.yml/badge.svg)](https://github.com/penquinspecz/SignalCraft/actions/workflows/docker-smoke.yml) [![Lint](https://github.com/penquinspecz/SignalCraft/actions/workflows/ruff.yml/badge.svg)](https://github.com/penquinspecz/SignalCraft/actions/workflows/ruff.yml)

**Deterministic Career Intelligence for Market Change**

SignalCraft is a deterministic career intelligence platform that tracks how the job
market changes over time. It monitors employer career pages, computes stable diffs
across runs, and surfaces temporal signals — which roles are emerging, which are
disappearing, how teams are shifting — with full provenance and replay verification.

**What makes it different:**
- **Temporal intelligence, not just matching.** Every run produces deterministic diffs
  against previous runs. Role evolution, team expansion, and market signals are
  tracked longitudinally.
- **Deterministic and replayable.** Same inputs produce byte-identical outputs.
  Every artifact is SHA256-verified. Replay verification runs offline.
- **Structured source preference.** Provider extraction prefers APIs and structured
  data (Ashby, JSON-LD) over HTML scraping. New providers are onboarded through a
  policy-aware factory with legal evaluation and receipts.
- **Contract-driven artifacts.** 21 versioned JSON schemas. UI-safe artifacts never
  contain raw job descriptions. Artifact categories (`ui_safe` vs `replay_safe`) are
  enforced at write boundaries.
- **Infrastructure portable.** Runs locally, in Docker, on AWS EKS, or on a k3s
  Pi cluster. CronJob-shaped batch execution with ephemeral state per run.

---

## What It Does

### Discovery

- Aggregates jobs from official first-party career sites (not paywalled/credentialed scraping)
- Normalizes and de-duplicates postings across providers
- Preserves provenance and replayable run artifacts for auditability

### Matching

- Applies deterministic scoring and ranking (matching engine)
- Produces explainability artifacts for score interpretation
- Keeps ordering stable and reproducible across equivalent inputs

### Intelligence

- Tracks temporal changes and emits structured diffs across retained runs
- Computes drift analytics (for example, skills rising/falling and role requirement shifts)
- Scales provider coverage via the provider onboarding factory (robots/TOS evaluation + scaffolding + receipts)
- Can layer bounded AI insights on top of structured artifacts (optional)

Capability narrative:
- For a target role family, SignalCraft can deterministically rank current openings with explainable reasons, then show how required skills and role attributes changed over recent windows with provenance-backed diffs.

Operational note:
- Every run produces inspectable artifacts under `state/runs/<run_id>/`.
- Canonical pipeline entrypoint: `scripts/run_daily.py`.

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [AI Workflow](docs/AI_WORKFLOW.md)
- [Operations](docs/OPERATIONS.md)
- [Candidates](docs/CANDIDATES.md)
- [Legal Positioning](docs/LEGAL_POSITIONING.md)
- [License](LICENSE)
- [Security Policy](SECURITY.md)

---

## Who It’s For

SignalCraft is designed for serious job seekers targeting top technology companies who want:

- A single pane of glass across elite employer career pages
- Deterministic ranking instead of opaque AI magic
- Explainable scoring outputs
- Historical tracking and change detection
- Infrastructure-grade reliability
- Guardrailed AI insights layered on top of real data

This is not a job board.
It is an intelligence layer over official sources.

---

## Core Principles

### Deterministic by Default
Same inputs → same outputs.
Every decision is logged, hashed, and replayable.

### AI Is Last-Mile
AI never replaces core logic.
AI reads structured artifacts and produces insight.
All AI outputs are cached, schema-validated, and guardrailed.

### Legality-Conscious by Design
SignalCraft:
- Links directly to original employer career pages
- Does not replace or masquerade as the source
- Respects provider policies, rate limits, and robots decisions
- Avoids scraping arms-race behavior

See [`docs/LEGAL_POSITIONING.md`](docs/LEGAL_POSITIONING.md) for the explicit design contract.

### Infrastructure-Grade Execution
- CI + Docker smoke validation
- Replayable run reports
- Snapshot debugging
- Kubernetes-native scheduling
- Object-store publishing
- Deterministic semantic augmentation

---

## Architecture

SignalCraft has two layers:

- **JIE (Job Intelligence Engine):** The deterministic core. Ingestion, scoring,
  diff computation, artifact emission, replay verification. Lives in `src/ji_engine/`.
- **SignalCraft:** The product surface. Dashboard API, alerts, digests, analytics
  artifacts. Lives in `src/jobintel/` and `src/ji_engine/dashboard/`.

### Data Flow

```text
Employer Career Pages -> Provider Ingestion (snapshot-first)
  -> Enrichment -> Classification -> Scoring (deterministic, versioned)
    -> Diff Engine (identity-normalized, vs previous run)
      -> Artifacts (schema-validated, categorized)
        -> Dashboard API / Notifications / Analytics
```

### Key Contracts

- **Determinism:** `PYTHONHASHSEED=0`, `TZ=UTC`. Scoring has zero time/random
  dependencies. Replay verification compares SHA256 hashes offline.
- **Artifact Safety:** UI-safe artifacts cannot contain raw JD text (enforced by
  `artifacts/catalog.py`). Secrets are scanned and redacted at write boundaries.
- **Provider Policy:** Each provider has a structured policy record (robots, TOS,
  rate limits, scrape mode). Live providers require onboarding receipts.

---

## What It Is Not

- Not a job board mirror
- Not an uncontrolled scraper
- Not AI hallucination-driven ranking
- Not a growth-hack scraping arms race

SignalCraft is a discovery and intelligence layer — not a replacement for official employer systems.

---

## Current Status

- **Phase:** Phase 2 Hardening (correction epoch)
- **Active milestones:** M25-M36 (provider availability, alerts, analytics,
  role taxonomy, UI v0)
- **Correction track:** Phase2-C1 through Phase2-C12 (security hardening,
  determinism gate upgrade, operational cleanup)
- **On-prem:** Parked pending hardware (M40-M41)
- **AI:** Stub provider only. Live AI blocked until readiness contract defined.
- **Providers:** 8 configured (Anthropic, OpenAI, Scale AI, Replit, Cohere,
  Hugging Face, Mistral, Perplexity). All snapshot-mode in default config.

See `docs/ROADMAP.md` for the full roadmap and `docs/DETERMINISM_CONTRACT.md`
for replay/determinism guarantees.

---

## Roadmap Direction

SignalCraft is evolving toward:

- Temporal intelligence artifacts and longitudinal analytics as the product anchor
- Multi-user isolation
- Resume/profile ingestion
- Profile-aware scoring
- Per-job AI recommendations
- Explainability-focused UI
- Consumer-grade user experience
- Expanded provider coverage across top technology companies
- Compliance-aware partnerships

Full roadmap:
[`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## License

SignalCraft is Source Available, not open source.

Use is governed by the SignalCraft Source Available License v1.0 in [`LICENSE`](LICENSE).

Commercial use, redistribution, derivative works, and competing hosted services are prohibited without written permission.

For licensing inquiries:
Contact Chris Menendez: https://www.linkedin.com/in/chmz/
