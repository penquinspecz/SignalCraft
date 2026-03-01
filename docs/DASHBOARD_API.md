# Dashboard API Contract

SignalCraft dashboard backend API. Backend-first UI readiness; no authentication or multi-user UX.

## Endpoints

### GET /version

Returns service identity and schema versions for UI readiness.

**Response** (200):
```json
{
  "service": "SignalCraft",
  "git_sha": "<sha or unknown>",
  "schema_versions": {
    "run_summary": 1,
    "run_health": 1
  },
  "build_timestamp": "<optional ISO timestamp>"
}
```

**Env vars** (optional):
- `JOBINTEL_GIT_SHA` or `GIT_SHA` — git commit SHA (default: `"unknown"`)
- `JOBINTEL_BUILD_TIMESTAMP` or `BUILD_TIMESTAMP` — build timestamp (optional)

---

### GET /healthz

Liveness probe.

**Response** (200): `{"status": "ok"}`

---

### GET /ui

Static UI v0 page (read-only). Uses only documented API endpoints.

**Response** (200): HTML page

---

### GET /v1/latest?candidate_id=...

Returns last successful run state for the candidate.

**Query params**:
- `candidate_id` (optional): default `local`. Must match `[a-z0-9_]{1,64}`.

**Response** (200):
- Local: `{"source": "local", "candidate_id": "<id>", "path": "<path>", "payload": <last_success JSON>}`
- S3: `{"source": "s3", "candidate_id": "<id>", "bucket": "...", "prefix": "...", "key": "...", "payload": <state>}`

**Failure modes**:
- 400: Invalid `candidate_id`
- 404: last_success not found (local or S3)

---

### GET /v1/profile?candidate_id=...

Returns UI-safe candidate profile projection.

**Query params**:
- `candidate_id` (optional): if omitted, resolves current active candidate pointer.

**Response** (200):
```json
{
  "candidate_id": "alice",
  "profile_schema_version": 1,
  "profile_hash": "<sha256>",
  "display_name": "Alice Example",
  "profile_fields": {
    "schema_version": 1,
    "seniority": "senior",
    "role_archetype": "staff_ic",
    "location": "remote",
    "skills": ["python", "leadership"]
  }
}
```

**Failure modes**:
- 400: Invalid `candidate_id`
- 404: Candidate profile not found
- 500: Invalid profile payload / active pointer

---

### PUT /v1/profile?candidate_id=...

Updates versioned profile fields under contract.

**Request body**:
```json
{
  "display_name": "Alice Example",
  "profile_fields": {
    "seniority": "senior",
    "role_archetype": "staff_ic",
    "location": "remote",
    "skills": ["python", "leadership"]
  }
}
```

**Response** (200):
- Same shape as `GET /v1/profile`, including updated deterministic `profile_hash`.

**Failure modes**:
- 400: Invalid request / no fields provided
- 404: Candidate profile not found
- 500: Profile update failed

---

### GET /runs?candidate_id=...

List runs for the candidate (index-backed when available).

**Query params**:
- `candidate_id` (optional): default `local`

**Response** (200): Array of run index objects (`run_id`, `timestamp`, `artifacts`, ...)

**Failure modes**:
- 400: Invalid `candidate_id`

---

### GET /runs/{run_id}?candidate_id=...

Run detail (index + run_report + costs + ai_prompt_version).

**Failure modes**:
- 400: Invalid `run_id` or `candidate_id`
- 404: Run not found
- 413: Run index payload too large
- 500: Invalid JSON or shape

---

### GET /runs/{run_id}/artifact/{name}?candidate_id=...

Fetch artifact by name (from index.json mapping).

**Failure modes**:
- 400: Invalid artifact name (path traversal, oversized)
- 404: Artifact not found
- 500: Invalid artifact mapping (e.g. path escape attempt)

---

### GET /runs/{run_id}/semantic_summary/{profile}?candidate_id=...

Semantic summary for a profile.

**Failure modes**:
- 404: Semantic summary not found
- 413: Payload too large
- 500: Invalid JSON or shape

---

### GET /v1/runs/{run_id}?candidate_id=...

Run receipt (proof bundle) for a run.

**Failure modes**:
- 400: Invalid `run_id` or `candidate_id`
- 404: Run not found
- 413: Payload too large
- 500: Invalid JSON or shape

---

### GET /v1/runs/{run_id}/artifacts?candidate_id=...

Stable artifact index for a run. Bounded: no raw artifact bodies.

**Query params**:
- `candidate_id` (optional): default `local`

**Response** (200):
```json
{
  "run_id": "<run_id>",
  "candidate_id": "<candidate_id>",
  "artifacts": [
    {
      "key": "run_summary.v1.json",
      "path": "run_summary.v1.json",
      "content_type": "application/json",
      "schema_version": 1,
      "size_bytes": 1234
    }
  ]
}
```

- `schema_version`: present only for known schema artifacts (run_summary, run_health, provider_availability, run_report)
- `size_bytes`: present only when file exists

**Failure modes**:
- 400: Invalid `run_id` or `candidate_id`
- 404: Run not found

---

### GET /v1/artifacts/latest/{provider}/{profile}?candidate_id=...

Artifact index for latest run by provider/profile.

**Response** (200):
- Local: `{"source": "local", "run_id": "...", "paths": [...]}`
- S3: `{"source": "s3", "bucket": "...", "prefix": "...", "keys": [...]}`

**Failure modes**:
- 400: Invalid `candidate_id`
- 404: No artifacts for provider/profile

---

### GET /v1/ui/latest?candidate_id=...&top_n=...

UI v0 aggregate payload for read-only rendering. Composes latest run summary, top jobs, explanation, provider availability, and run health in one bounded response.

**Query params**:
- `candidate_id` (optional): default `local`
- `top_n` (optional): default `10`, min `1`, max `50`

**Response** (200):
```json
{
  "candidate_id": "local",
  "run_id": "2026-01-22T00:00:00Z",
  "latest_source": "local",
  "run": {
    "run_id": "2026-01-22T00:00:00Z",
    "timestamp": "2026-01-22T00:00:00Z",
    "status": "success",
    "semantic_enabled": true,
    "semantic_mode": "boost",
    "ai_prompt_version": "weekly_insights_v3",
    "cost_summary": {"total_estimated_tokens": 288}
  },
  "top_jobs": [],
  "top_jobs_artifact": "openai_ranked_jobs.cs.json",
  "explanation": {},
  "provider_availability": {},
  "run_health": {}
}
```

**Failure modes**:
- 400: Invalid `candidate_id` or `top_n`
- 404: latest run pointer missing `run_id`
- 413: referenced UI artifact payload too large
- 500: invalid JSON/shape or fail-closed UI-safe violation

---

## Fail-Closed & Bounded Reads

- **Read-time validation**: Artifacts are validated against schema/shape on read. Invalid payloads are rejected (500).
- **Bounded JSON**: `JOBINTEL_DASHBOARD_MAX_JSON_BYTES` (default 2MB) caps payload size. Oversized returns 413.
- **UI aggregate bounds**: `/v1/ui/latest` applies the same bounded-read limit per referenced artifact and returns 413 when exceeded.
- **Path traversal**: Artifact names are validated; `..` and absolute paths are rejected (500).
- **Candidate ID**: Strict sanitization via `[a-z0-9_]{1,64}`. Invalid values return 400.
- **UI-safe profile contract**: `/v1/profile` returns only contracted fields and hash, never raw resume/LinkedIn text.

## Run Proof Script

```bash
# Start dashboard: make dashboard
# Then run:
./scripts/dev/curl_dashboard_proof.sh
```

## See Also

- `docs/proof/m17-artifact-index-endpoint-2026-02-14.md` — artifact index endpoint proof
- `src/ji_engine/dashboard/app.py` — implementation
