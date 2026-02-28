# M30 Resume Ingestion v1 Proof (2026-02-28)

## Scope
Milestone 30 delivers offline, bounded resume ingestion with structured-only persistence.

## Redaction Boundary Statement
- Resume ingestion is local-only (`--resume-file`); no remote URL fetch path exists.
- Raw resume content is extracted in-process and discarded.
- Persisted outputs contain only structured fields + deterministic hashes.
- No raw resume text is written to run artifacts or CLI output.

## Artifacts
- Candidate profile: `state/candidates/<candidate_id>/inputs/candidate_profile.json`
- Structured resume artifact: `state/candidates/<candidate_id>/inputs/artifacts/resume_structured_<hash>.v1.json`
- Schema: `schemas/resume.schema.v1.json`

## Tests
- `tests/test_resume_ingestion_v1.py::test_resume_ingestion_structured_only_no_raw_leak`
- `tests/test_resume_ingestion_v1.py::test_resume_hash_stability_and_change_detection`
- `tests/test_resume_ingestion_v1.py::test_resume_ingestion_candidate_isolation`
- `tests/test_resume_ingestion_v1.py::test_resume_ingestion_pdf_supported`

## Example Payload Snippet
```json
{
  "resume_schema_version": 1,
  "candidate_id": "alice",
  "source_format": "pdf",
  "hash_version": "resume_hash.v1",
  "parser_version": "resume_parser.v1",
  "resume_hash": "<sha256>",
  "skills": ["python", "kubernetes"],
  "role_signals": ["software engineer"],
  "experience_summary": {
    "years_experience_estimate": 7,
    "seniority_signal": "senior"
  },
  "education_signals": ["bachelor"],
  "certification_signals": []
}
```
