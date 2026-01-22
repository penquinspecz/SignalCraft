# Run Report Reference

Run reports are written to `state/runs/<run_id>.json` and include metadata for reproducibility,
debugging, and audit trails. They are versioned with `run_report_schema_version`.

## Schema version
`run_report_schema_version`: integer. Current version: **1**.

## Top-level fields
- `run_id`: ISO timestamp used to identify the run.
- `status`: status string (`success`, `short_circuit`, `error`).
- `success`: boolean derived from status.
- `failed_stage`: present when status is `error`.
- `profiles`: list of profiles processed (e.g., `["cs"]`).
- `providers`: list of providers processed (e.g., `["openai"]`).
- `flags`: CLI flags and thresholds (including `min_score`, `min_alert_score`).
- `timestamps`: `started_at`, `ended_at`.
- `stage_durations`: per-stage timings.
- `diff_counts`: per-profile diff counts (new/changed/removed).
- `provenance_by_provider`: scrape provenance (snapshot/live, hashes, parsed counts).
- `selection`: top-level selection summary including:
  - `scrape_provenance`
  - `classified_job_count`
  - `classified_job_count_by_provider`
- `inputs`: raw/labeled/enriched input file metadata (path, mtime, sha256).
- `outputs_by_profile`: ranked outputs (paths + sha256).
- `inputs_by_provider`, `outputs_by_provider`: provider-specific input/output metadata.
- `scoring_inputs_by_profile`: selected scoring input metadata (path/mtime/sha256).
- `scoring_input_selection_by_profile`: decision metadata for scoring inputs:
  - `selected_path`
  - `candidate_paths_considered` (path/mtime/sha/exists)
  - `selection_reason` (enum string)
  - `comparison_details` (e.g., newer_by_seconds, prefer_ai)
  - `decision` (human-readable rule and reason)
- `delta_summary`: delta intelligence summary if available.
- `git_sha`: best-effort git sha when available.
- `image_tag`: container image tag if set.
- `s3_bucket`, `s3_prefixes`, `uploaded_files_count`, `dashboard_url`: S3 publishing metadata (when enabled).

## Selection reason enums
Selection reasons are deterministic strings such as:
- `ai_only`
- `no_enrich_enriched_newer`
- `no_enrich_labeled_newer_or_equal`
- `no_enrich_enriched_only`
- `no_enrich_labeled_only`
- `no_enrich_missing`
- `default_enriched_required`
- `default_enriched_missing`
- `prefer_ai_enriched`

## How to debug a run
Use these paths to inspect artifacts:

- Run report:
  - `state/runs/<run_id>.json`
- Run registry:
  - `state/runs/<run_id>/index.json`
- Ranked outputs:
  - `data/<provider>_ranked_jobs.<profile>.json`
  - `data/<provider>_ranked_jobs.<profile>.csv`
  - `data/<provider>_ranked_families.<profile>.json`
  - `data/<provider>_shortlist.<profile>.md`
  - `data/<provider>_top.<profile>.md`
- Alerts:
  - `data/<provider>_alerts.<profile>.json`
  - `data/<provider>_alerts.<profile>.md`
- AI insights (when enabled):
  - `state/runs/<run_id>/ai_insights.<profile>.json`
  - `state/runs/<run_id>/ai_insights.<profile>.md`
- AI job briefs (when enabled):
  - `state/runs/<run_id>/ai_job_briefs.<profile>.json`
  - `state/runs/<run_id>/ai_job_briefs.<profile>.md`

## Replayability
To validate reproducibility:
```bash
python scripts/replay_run.py --run-id <run_id> --profile cs
```
- Exit code `0`: reproducible
- Exit code `2`: missing inputs or mismatched hashes
- Exit code `>=3`: runtime error
