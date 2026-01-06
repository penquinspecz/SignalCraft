#!/usr/bin/env python3
"""
Smoke test: Fetch one job posting via API and verify cache and data.

Tests the specific job: https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630/application
"""

import sys
from pathlib import Path

from ji_engine.config import DATA_DIR
from ji_engine.integrations.ashby_graphql import fetch_job_posting
from ji_engine.integrations.html_to_text import html_to_text

ORG = "openai"
JOB_ID = "0c22b805-3976-492e-81f2-7cf91f63a630"
CACHE_DIR = DATA_DIR / "ashby_cache"


def main():
    """Fetch one job and verify results."""
    print(f"Smoke test: Fetching job {JOB_ID} from {ORG}...")
    print()
    
    # Fetch via API
    try:
        data = fetch_job_posting(org=ORG, job_id=JOB_ID, cache_dir=CACHE_DIR)
    except Exception as e:
        print(f"❌ API fetch failed: {e}")
        sys.exit(1)
    
    # Extract job posting data
    jp = (data.get("data") or {}).get("jobPosting") or {}
    
    title = jp.get("title")
    has_description_html = bool(jp.get("descriptionHtml"))
    description_html = jp.get("descriptionHtml") or ""
    description_html_chars = len(description_html)
    
    # Convert to text
    jd_text = html_to_text(description_html) if description_html else ""
    jd_text_chars = len(jd_text)
    
    # Check cache file
    cache_path = CACHE_DIR / f"{JOB_ID}.json"
    cache_exists = cache_path.exists()
    cache_size = cache_path.stat().st_size if cache_exists else 0
    
    # Print results
    print("Results:")
    print(f"  Title: {title}")
    print(f"  Has descriptionHtml: {has_description_html}")
    print(f"  descriptionHtml chars: {description_html_chars}")
    print(f"  jd_text chars: {jd_text_chars}")
    print()
    print("Cache:")
    print(f"  Cache file exists: {cache_exists}")
    print(f"  Cache file path: {cache_path}")
    print(f"  Cache file size: {cache_size} bytes")
    print()
    
    # Validation
    success = True
    if not title:
        print("❌ FAIL: No title found")
        success = False
    if not has_description_html:
        print("❌ FAIL: descriptionHtml missing")
        success = False
    if description_html_chars == 0:
        print("❌ FAIL: descriptionHtml is empty")
        success = False
    if not cache_exists:
        print("❌ FAIL: Cache file does not exist")
        success = False
    if cache_size < 1000:
        print(f"❌ FAIL: Cache file too small ({cache_size} bytes, expected >= 1000)")
        success = False
    
    if success:
        print("✅ All checks passed!")
        return 0
    else:
        print("❌ Some checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
