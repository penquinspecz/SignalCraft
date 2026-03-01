# Role Drift Analytics v1 Proof (2026-02-28)

## Scope
Role Drift Analytics v1 adds deterministic company-level trend summaries from job timeline artifacts:
- rising/falling skill token trends over 7/14/30 day windows
- seniority/location shift role summaries
- digest integration via `company_drift_highlights`

## Artifact Paths
- `state/candidates/<candidate_id>/runs/<run_id>/artifacts/role_drift_v1.json`
- `state/candidates/<candidate_id>/runs/<run_id>/artifacts/digest_v1.json` (`company_drift_highlights` section)

For default-candidate compatibility, artifacts may also appear under:
- `state/runs/<run_id>/artifacts/role_drift_v1.json`
- `state/runs/<run_id>/artifacts/digest_v1.json`

## Tests
- `tests/test_role_drift_artifact_v1.py::test_role_drift_payload_is_deterministic`
- `tests/test_role_drift_artifact_v1.py::test_role_drift_aggregation_from_timeline_fixture`
- `tests/test_digest_artifact_v1.py::test_digest_artifact_deterministic_and_no_jd_leak`

## Example Payload Snippet
```json
{
  "role_drift_schema_version": 1,
  "candidate_id": "local",
  "windows": {
    "last_30_days": {
      "window_days": 30,
      "companies": [
        {
          "company_key": "openai::acme",
          "skills_rising": [
            {"token": "python", "count": 2}
          ],
          "skills_falling": [
            {"token": "flask", "count": 1}
          ],
          "seniority_shift_roles": ["Staff Platform Engineer"],
          "location_shift_roles": ["Senior Platform Engineer"]
        }
      ]
    }
  }
}
```
