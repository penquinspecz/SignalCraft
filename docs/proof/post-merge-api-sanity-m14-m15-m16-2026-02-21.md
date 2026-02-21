# Post-Merge API Sanity (M14/M15/M16) — 2026-02-21

## Scope
- Verify artifact catalog coverage for:
  - `explanation_v1.json`
  - AI insights artifacts (`ai_insights.*.json`)
  - AI job brief artifacts (`ai_job_briefs.*.json`) including fail-closed error artifact.
- Run dashboard smoke for artifact index + bounded artifact fetch.

## 1) Artifact Catalog Coverage
Command:
```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from ji_engine.artifacts.catalog import get_artifact_category
for k in [
  'explanation_v1.json',
  'ai_insights.cs.json',
  'ai_job_briefs.cs.json',
  'ai_job_briefs.cs.error.json',
]:
    print(f"{k} -> {get_artifact_category(k)}")
PY
```

Output excerpt:
```text
explanation_v1.json -> ui_safe
ai_insights.cs.json -> ui_safe
ai_job_briefs.cs.json -> ui_safe
ai_job_briefs.cs.error.json -> ui_safe
```

Code pointers:
- `src/ji_engine/artifacts/catalog.py`:
  - explicit entry for `explanation_v1.json`
  - pattern entries for `*ai_insights*.json` and `*ai_job_briefs*.json`

## 2) Dashboard Smoke Attempt (local main)
Documented dev start method:
```bash
make dashboard
```

Observed output:
```text
Dashboard deps missing (fastapi, uvicorn). Install with: pip install -e '.[dashboard]'
make: *** [dashboard] Error 2
```

Attempted dependency install:
```bash
.venv/bin/python -m pip install -e '.[dashboard]'
```

Observed output excerpt:
```text
ERROR: Could not find a version that satisfies the requirement setuptools>=68
ERROR: No matching distribution found for setuptools>=68
```

Interpretation:
- Environment is network-restricted; dashboard extras could not be installed.
- Live API process could not be started, so endpoint-level curl smoke is blocked in this environment.

## 3) Curl Commands + Endpoint Output Excerpts
Commands attempted:
```bash
/usr/bin/curl -sS -m 2 -w "\nHTTP_STATUS:%{http_code}\n" \
  "http://127.0.0.1:8011/v1/runs/2026-02-21T12:00:00Z/artifacts?candidate_id=local"
/usr/bin/curl -sS -m 2 -w "\nHTTP_STATUS:%{http_code}\n" \
  "http://127.0.0.1:8011/runs/2026-02-21T12:00:00Z/artifact/explanation_v1.json?candidate_id=local"
/usr/bin/curl -sS -m 2 -w "\nHTTP_STATUS:%{http_code}\n" \
  "http://127.0.0.1:8011/runs/2026-02-21T12:00:00Z/artifact/ai_insights.cs.json?candidate_id=local"
/usr/bin/curl -sS -m 2 -w "\nHTTP_STATUS:%{http_code}\n" \
  "http://127.0.0.1:8011/runs/2026-02-21T12:00:00Z/artifact/ai_job_briefs.cs.json?candidate_id=local"
/usr/bin/curl -sS -m 2 -w "\nHTTP_STATUS:%{http_code}\n" \
  "http://127.0.0.1:8011/runs/2026-02-21T12:00:00Z/artifact/ai_job_briefs.cs.error.json?candidate_id=local"
```

Observed output excerpt (all endpoints):
```text
curl: (7) Failed to connect to 127.0.0.1 port 8011 ...
HTTP_STATUS:000
```

## 4) Forbidden Field / Raw JD Guard (fixture payload check)
Command:
```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path
from ji_engine.artifacts.catalog import assert_no_forbidden_fields
run_dir=Path('/tmp/postmerge_api_sanity_m14_m15_m16_2026-02-21/state/candidates/local/runs/20260221T120000Z')
for rel in ['artifacts/explanation_v1.json','ai_insights.cs.json','ai_job_briefs.cs.json','ai_job_briefs.cs.error.json']:
    payload=json.loads((run_dir/rel).read_text(encoding='utf-8'))
    assert_no_forbidden_fields(payload, context=rel)
    print(f'PASS no_forbidden_fields {rel}')
PY
```

Output excerpt:
```text
PASS no_forbidden_fields artifacts/explanation_v1.json
PASS no_forbidden_fields ai_insights.cs.json
PASS no_forbidden_fields ai_job_briefs.cs.json
PASS no_forbidden_fields ai_job_briefs.cs.error.json
```

## Result
- Catalog recognition checks: PASS.
- Local live dashboard curl smoke: BLOCKED by missing dashboard extras in a network-restricted environment.
- No raw JD / forbidden fields found in the exercised fixture artifacts.
