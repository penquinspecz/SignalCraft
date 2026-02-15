# Artifact Model v2

Contract-first definition of UI-safe vs replay-safe artifacts (Milestone 11).

## Overview

Artifacts are split into two categories:

| Category | Purpose | Prohibited | Examples |
|----------|---------|------------|----------|
| **UI-safe** | Consumed by dashboard, notifications, external systems | Raw JD, secrets | Insights input, shortlist summaries |
| **Replay-safe** | Required for deterministic replay verification | None (may contain full data) | Run report, scoring inputs, config |

## UI-Safe Artifacts

**Definition**: Artifacts safe to expose to UI, notifications, or external consumers.

**Prohibited fields** (must NOT appear in job items or equivalent):
- `jd_text` — raw job description text
- `description` — full job description
- `description_text` — alternative description field
- `descriptionHtml` — HTML job description
- `job_description` — legacy description field
- Secrets, API keys, bearer tokens (enforced by redaction guard)

**Allowed**: `title`, `job_id`, `score`, `apply_url`, `location`, `team`, `fit_signals`, `risk_signals`, `jd_text_chars` (character count only).

**Schema**: `schemas/ui_safe_artifact.schema.v1.json`

## Replay-Safe Artifacts

**Definition**: Artifacts required for replay verification. May contain full job data, config, and hashes.

**Purpose**: Deterministic replay, drift detection, audit.

**Schema**: `schemas/replay_safe_artifact.schema.v1.json`

## Current Artifact Categorization

| Artifact | Category | Notes |
|----------|----------|-------|
| run_summary | Not yet categorized | Pointers only; targets may be UI or replay |
| run_health | Not yet categorized | Metadata; low sensitivity |
| run_report | Not yet categorized | Contains full provenance; replay-critical |
| ranked_json | Not yet categorized | May contain jd_text; pipeline output |
| ranked_csv | Not yet categorized | Typically summary fields |
| shortlist_md | Not yet categorized | Human-readable; may need redaction |
| insights_input | UI-safe | Explicitly excludes raw JD |
| enriched_jobs | Not yet categorized | Contains enrichment metadata |

## Backward Compatibility Policy

- **v1 → v2**: New schema versions are additive. Existing artifacts remain valid.
- **Emission**: New artifact types use new filenames (e.g. `artifact_ui_safe.v1.json`).
- **Run summary pointers**: New artifact keys added to `primary_artifacts` / `quicklinks` in a backward-compatible way (optional fields).
- **Readers**: Must tolerate missing v2 artifacts; may derive UI-safe projection from run_report when v2 not present.

## Verification

```bash
.venv/bin/python -m pytest tests/test_artifact_model_v2.py -v
```
