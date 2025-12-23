"""Test fallback URL derivation for HTML enrichment."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.enrich_jobs import _derive_fallback_url


def test_fallback_url_derivation():
    apply_url = "https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630/application"
    expected = "https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630"
    assert _derive_fallback_url(apply_url) == expected


if __name__ == "__main__":
    test_fallback_url_derivation()
    print("\n✅ Fallback URL derivation test passed!")
