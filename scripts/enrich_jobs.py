#!/usr/bin/env python3
"""
Enrich labeled jobs by fetching job data via Ashby GraphQL API.

Falls back to HTML base page when API returns missing/empty descriptionHtml.
If API returns jobPosting null, mark unavailable and do NOT HTML-fallback.

Usage:
  python -m scripts.enrich_jobs
  python scripts/enrich_jobs.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from ji_engine.config import ASHBY_CACHE_DIR, ENRICHED_JOBS_JSON, LABELED_JOBS_JSON
from ji_engine.integrations.ashby_graphql import fetch_job_posting
from ji_engine.integrations.html_to_text import html_to_text

DEBUG = os.getenv("JI_DEBUG") == "1"

ORG = "openai"
CACHE_DIR = ASHBY_CACHE_DIR


def _extract_job_id_from_url(url: str) -> Optional[str]:
    """
    Extract jobPostingId from apply_url using regex pattern.
    Pattern: /openai/([0-9a-f-]{36})/application
    """
    pattern = r"/openai/([0-9a-f-]{36})/application"
    match = re.search(pattern, url, re.IGNORECASE)
    return match.group(1) if match else None


def _derive_fallback_url(apply_url: str) -> str:
    """Derive base posting URL (without /application) for HTML fallback."""
    return apply_url[:-len("/application")] if apply_url.endswith("/application") else apply_url


def _fetch_html_fallback(url: str) -> Optional[str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) "
            "Gecko/20100101 Firefox/146.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        html = resp.text
        html_lower = html.lower()
        if "<html" not in html_lower and "<!doctype" not in html_lower:
            return None
        return html
    except Exception as e:
        print(f" ⚠️ HTML fallback fetch failed: {e}")
        return None


def _extract_jd_from_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")

    selectors = [
        "div[data-testid='jobPostingDescription']",
        "main",
        "article",
    ]

    for selector in selectors:
        container = soup.select_one(selector)
        if container:
            for tag in container.find_all(["script", "style"]):
                tag.decompose()
            text = container.get_text(separator="\n", strip=True)
            if text and len(text) > 200:
                return text

    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text if text and len(text) > 200 else None


def _apply_api_response(
    job: Dict[str, Any],
    api_data: Dict[str, Any] | None,
    fallback_url: str,
) -> Tuple[Dict[str, Any], bool]:
    """
    Returns (updated_job, fallback_needed)
    """
    updated = dict(job)
    updated.setdefault("enrich_status", None)
    updated.setdefault("enrich_reason", None)

    clean_title = job.get("title")
    location = job.get("location")
    team = job.get("team")
    jd_text: Optional[str] = None

    if not api_data or api_data.get("errors"):
        updated["enrich_status"] = "failed"
        updated["enrich_reason"] = "api_errors" if api_data and api_data.get("errors") else "api_fetch_failed"
        updated.update({"title": clean_title, "location": location, "team": team, "jd_text": jd_text})
        return updated, True

    jp = (api_data.get("data") or {}).get("jobPosting")
    if jp is None:
        if DEBUG:
            print(" jobPosting is null (likely unlisted/blocked/removed); marking unavailable")
            print(f" fallback_url: {fallback_url}")
        updated["enrich_status"] = "unavailable"
        updated["enrich_reason"] = "api_jobPosting_null"
        updated.update({"title": clean_title, "location": location, "team": team, "jd_text": None})
        return updated, False  # do NOT HTML-fallback

    clean_title = jp.get("title") or clean_title
    location = jp.get("locationName") or location

    team_names = jp.get("teamNames")
    if isinstance(team_names, list) and team_names:
        team_str = ", ".join([t for t in team_names if isinstance(t, str) and t.strip()])
        team = team_str if team_str else team

    description_html = (jp.get("descriptionHtml") or "").strip()
    if description_html:
        jd_text = html_to_text(description_html)
        if jd_text:
            updated["enrich_status"] = "enriched"
            updated["enrich_reason"] = None
            updated.update({"title": clean_title, "location": location, "team": team, "jd_text": jd_text})
            return updated, False
        else:
            if DEBUG:
                print(" descriptionHtml converted to empty text - falling back to HTML")
            updated["enrich_status"] = "failed"
            updated["enrich_reason"] = "description_html_empty_text"
            updated.update({"title": clean_title, "location": location, "team": team, "jd_text": None})
            return updated, True

    if DEBUG:
        print(" descriptionHtml missing/empty; falling back to HTML base page")
        print(f" fallback_url: {fallback_url}")
    updated["enrich_status"] = "failed"
    updated["enrich_reason"] = "description_html_missing"
    updated.update({"title": clean_title, "location": location, "team": team, "jd_text": None})
    return updated, True


def main() -> int:
    if not LABELED_JOBS_JSON.exists():
        print(f"Error: Input file not found: {LABELED_JOBS_JSON}")
        return 1

    jobs = json.loads(LABELED_JOBS_JSON.read_text(encoding="utf-8"))
    enriched: List[Dict[str, Any]] = []
    stats = {"enriched": 0, "unavailable": 0, "failed": 0}

    filtered_jobs = [j for j in jobs if j.get("relevance") in ("RELEVANT", "MAYBE")]

    print(f"Loaded {len(jobs)} labeled jobs")
    print(f"Filtering for RELEVANT/MAYBE: {len(filtered_jobs)} jobs to enrich\n")

    for i, job in enumerate(filtered_jobs, 1):
        apply_url = job.get("apply_url", "")
        if not apply_url:
            print(f" [{i}/{len(filtered_jobs)}] Skipping - no apply_url")
            enriched.append({**job, "jd_text": None, "fetched_at": None})
            continue

        print(f" [{i}/{len(filtered_jobs)}] Processing: {job.get('title', 'Unknown')}")

        job_id = _extract_job_id_from_url(apply_url)
        if not job_id:
            print(" ⚠️ Cannot extract jobPostingId from URL - not enrichable")
            print(f" URL: {apply_url}")
            enriched.append({**job, "jd_text": None, "fetched_at": None})
            continue

        fallback_url = _derive_fallback_url(apply_url)

        try:
            api_data = fetch_job_posting(org=ORG, job_id=job_id, cache_dir=CACHE_DIR)
        except Exception as e:
            print(f" ❌ API fetch failed: {e}")
            api_data = None

        updated_job, fallback_needed = _apply_api_response(job, api_data, fallback_url)
        jd_text = updated_job.get("jd_text")

        if fallback_needed:
            print(" ⚠️ Falling back to HTML parsing")
            if DEBUG:
                print(f" fallback_url: {fallback_url}")
            html = _fetch_html_fallback(fallback_url)
            if html:
                jd_text = _extract_jd_from_html(html)
                if jd_text:
                    print(f" ✅ Extracted from HTML: {len(jd_text)} chars")
                    updated_job["jd_text"] = jd_text
                    updated_job["enrich_status"] = "enriched"
                    updated_job["enrich_reason"] = updated_job.get("enrich_reason") or "html_fallback"
                else:
                    print(" ❌ HTML extraction failed")
                    updated_job["enrich_status"] = updated_job.get("enrich_status") or "failed"
                    updated_job["enrich_reason"] = updated_job.get("enrich_reason") or "html_extraction_failed"
            else:
                print(" ❌ HTML fetch failed")
                updated_job["enrich_status"] = updated_job.get("enrich_status") or "failed"
                updated_job["enrich_reason"] = updated_job.get("enrich_reason") or "html_fetch_failed"

        if updated_job.get("enrich_status") == "unavailable":
            jd_text = None

        updated_job["fetched_at"] = datetime.utcnow().isoformat()

        if jd_text:
            print(f" ✅ Final JD length: {len(jd_text)} chars")
            stats["enriched"] += 1
        else:
            status = updated_job.get("enrich_status")
            if status == "unavailable":
                stats["unavailable"] += 1
            else:
                stats["failed"] += 1
            print(" ❌ No JD text extracted")

        enriched.append(updated_job)

    ENRICHED_JOBS_JSON.parent.mkdir(parents=True, exist_ok=True)
    ENRICHED_JOBS_JSON.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("Enrichment Summary:")
    print(f" Total processed: {len(enriched)}")
    print(f" Enriched: {stats['enriched']}")
    print(f" Unavailable: {stats['unavailable']}")
    print(f" Failed: {stats['failed']}")
    print(f" Output: {ENRICHED_JOBS_JSON}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())