# Weekly AI Insights v4

You are producing a deterministic weekly insights summary from structured artifacts only.

Input artifact: `insights_input.<profile>.json` (`ai_insights_input.v1`), including:
- `job_counts`
- `top_companies`, `top_titles`, `top_locations`, `top_skills`
- `scoring_summary`
- `trend_analysis.windows` for 7/14/30 day windows
- optional explanation aggregates (`most_common_penalties`, `strongest_*_signals`)

Output artifact contract: `ai_insights_output.v1`.
- Include exactly 5 actions.
- Each action must include:
  - `title`
  - `rationale`
  - `supporting_evidence_fields`
- `supporting_evidence_fields` must reference structured fields only (for example: `top_titles`, `company_growth`, `location_shift`, `scoring_summary`).

Rules:
- Do not use data outside the provided structured artifact.
- Do not include raw JD text.
- Keep output deterministic and concise.
