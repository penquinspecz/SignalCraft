# M29 Candidate Profile UX v1 Proof (2026-02-28)

## Scope
Milestone 29 backend-first profile loop:
- deterministic profile hash
- candidate create/list/switch/update CLI workflow
- `/v1/profile` read/write contract
- `/v1/latest` candidate-aware response

## Curl Simulation (UI-free)

```bash
# 1) read active candidate profile
curl -s "http://localhost:8000/v1/profile" | jq .

# 2) update one candidate profile contract
curl -s -X PUT "http://localhost:8000/v1/profile?candidate_id=alice" \
  -H "content-type: application/json" \
  -d '{
    "display_name": "Alice Product",
    "profile_fields": {
      "seniority": "senior",
      "role_archetype": "staff_ic",
      "location": "remote",
      "skills": ["python", "leadership", "distributed systems"]
    }
  }' | jq .

# 3) confirm candidate-aware latest pointer
curl -s "http://localhost:8000/v1/latest?candidate_id=alice" | jq .
```

## Example JSON Snippet

```json
{
  "candidate_id": "alice",
  "profile_schema_version": 1,
  "profile_hash": "<sha256>",
  "display_name": "Alice Product",
  "profile_fields": {
    "schema_version": 1,
    "seniority": "Senior",
    "role_archetype": "Staff IC",
    "location": "Remote",
    "skills": [
      "distributed systems",
      "leadership",
      "python"
    ]
  }
}
```

## Test Evidence
- `tests/test_candidates_cli.py::test_candidate_create_switch_update_and_hash_stability`
- `tests/test_candidates_cli.py::test_candidate_profile_hash_isolation_per_candidate`
- `tests/test_dashboard_app.py::test_dashboard_profile_get_put_contract`
- `tests/test_dashboard_app.py::test_dashboard_profile_candidate_isolation`
- `tests/test_dashboard_app.py::test_dashboard_latest_local_candidate_query_returns_candidate_id`
