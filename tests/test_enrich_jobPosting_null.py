"""Test handling of jobPosting null response."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.enrich_jobs import _apply_api_response


def test_jobposting_null_marks_unavailable_no_fallback():
    fixture_path = ROOT / "tests" / "fixtures" / "ashby_jobPosting_null.json"
    api_data = json.loads(fixture_path.read_text(encoding="utf-8"))

    job = {
        "title": "Original Title",
        "location": "Original Location",
        "team": "Original Team",
        "apply_url": "https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630/application",
    }
    fallback_url = "https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630"

    updated, fallback_needed = _apply_api_response(job, api_data, fallback_url)

    assert updated.get("enrich_status") == "unavailable"
    assert updated.get("enrich_reason") == "api_jobPosting_null"
    assert updated.get("jd_text") is None
    assert fallback_needed is False


if __name__ == "__main__":
    test_jobposting_null_marks_unavailable_no_fallback()
    print("\n✅ jobPosting null handling test passed!")
