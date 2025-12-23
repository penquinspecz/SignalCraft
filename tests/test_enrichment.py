"""Unit tests for enrichment pipeline."""

from pathlib import Path
import sys

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ji_engine.pipeline.enrichment import _extract_job_id_from_url


def test_extract_job_id_from_url():
    """Test that jobPostingId is correctly extracted from apply_url using regex."""
    
    # Real apply_url from OpenAI jobs
    real_apply_url = "https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630/application"
    expected_job_id = "0c22b805-3976-492e-81f2-7cf91f63a630"
    
    # Test extraction
    job_id = _extract_job_id_from_url(real_apply_url)
    assert job_id == expected_job_id, f"Expected {expected_job_id}, got {job_id}"
    
    # Test with different case (should still work due to re.IGNORECASE)
    uppercase_url = "https://jobs.ashbyhq.com/openai/0C22B805-3976-492E-81F2-7CF91F63A630/application"
    job_id_upper = _extract_job_id_from_url(uppercase_url)
    assert job_id_upper == "0C22B805-3976-492E-81F2-7CF91F63A630", f"Expected uppercase UUID, got {job_id_upper}"
    
    # Test invalid URLs (should return None)
    invalid_urls = [
        "https://jobs.ashbyhq.com/openai/",  # No UUID
        "https://jobs.ashbyhq.com/openai/123/application",  # Too short
        "https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630",  # Missing /application
        "https://example.com/job/123",  # Wrong domain
        "https://jobs.ashbyhq.com/anthropic/0c22b805-3976-492e-81f2-7cf91f63a630/application",  # Wrong path
    ]
    
    for invalid_url in invalid_urls:
        job_id = _extract_job_id_from_url(invalid_url)
        assert job_id is None, f"Expected None for invalid URL '{invalid_url}', got {job_id}"
    
    print("\n✅ All tests passed: jobPostingId extraction works correctly")


if __name__ == "__main__":
    test_extract_job_id_from_url()
