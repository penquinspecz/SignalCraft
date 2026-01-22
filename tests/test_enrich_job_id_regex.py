"""Test job ID extraction regex."""

import sys
from pathlib import Path

# Add root to path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.enrich_jobs import _extract_job_id_from_url


def test_extract_job_id_valid_url():
    """Test that regex extracts UUID from valid OpenAI Ashby URL."""
    url = "https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630/application"
    expected = "0c22b805-3976-492e-81f2-7cf91f63a630"

    result = _extract_job_id_from_url(url)
    assert result == expected, f"Expected {expected}, got {result}"


def test_extract_job_id_case_insensitive():
    """Test that regex works with uppercase UUID."""
    url = "https://jobs.ashbyhq.com/openai/0C22B805-3976-492E-81F2-7CF91F63A630/application"
    expected = "0C22B805-3976-492E-81F2-7CF91F63A630"

    result = _extract_job_id_from_url(url)
    assert result == expected, f"Expected {expected}, got {result}"


def test_extract_job_id_invalid_urls():
    """Test that regex returns None for invalid URLs."""
    invalid_urls = [
        "https://jobs.ashbyhq.com/openai/",  # No UUID
        "https://jobs.ashbyhq.com/openai/123/application",  # Too short
        "https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630",  # Missing /application
        "https://example.com/job/123",  # Wrong domain
        "https://jobs.ashbyhq.com/anthropic/0c22b805-3976-492e-81f2-7cf91f63a630/application",  # Wrong org
        "",  # Empty string
    ]

    for url in invalid_urls:
        result = _extract_job_id_from_url(url)
        assert result is None, f"Expected None for '{url}', got {result}"


if __name__ == "__main__":
    test_extract_job_id_valid_url()
    test_extract_job_id_case_insensitive()
    test_extract_job_id_invalid_urls()
    print("\n✅ All regex tests passed!")
