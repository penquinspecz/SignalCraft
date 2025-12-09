from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from ji_engine.models import RawJobPosting, JobSource


CAREERS_SEARCH_URL = "https://openai.com/careers/search/"


class OpenAICareersProvider:
    """
    Simple scraper for https://openai.com/careers/search/

    MVP strategy:
      - Fetch the search page
      - Find anchors pointing to jobs.ashbyhq.com (the Apply links)
      - Use the nearby text as our job title
      - For Sprint 1, we keep title + URL; we can follow detail links later.
    """

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def fetch_raw_html(self) -> str:
        headers = {
            "User-Agent": "job-intelligence-engine/0.1 (+personal project)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        resp = requests.get(CAREERS_SEARCH_URL, headers=headers, timeout=self.timeout)

        if resp.status_code != 200:
            print(f"[OpenAICareersProvider] HTTP {resp.status_code} when fetching {CAREERS_SEARCH_URL}")
            snippet = resp.text[:500].replace("\n", " ") if resp.text else ""
            print(f"[OpenAICareersProvider] Response snippet: {snippet}")
            resp.raise_for_status()

        return resp.text


    def parse_listings(self, html: str) -> List[RawJobPosting]:
        soup = BeautifulSoup(html, "html.parser")

        # Jobs are surfaced with "Apply now" links pointing to jobs.ashbyhq.com
        apply_links = soup.find_all("a", href=lambda h: h and "jobs.ashbyhq.com" in h)

        results: List[RawJobPosting] = []
        now = datetime.utcnow()

        for apply_tag in apply_links:
            apply_url = apply_tag.get("href")

            # Try to find the preceding anchor as the title.
            title_tag = apply_tag.find_previous("a")
            if not title_tag or title_tag is apply_tag:
                title_text = apply_tag.get_text(strip=True)
                detail_url: Optional[str] = apply_url
            else:
                title_text = title_tag.get_text(strip=True)
                detail_url = title_tag.get("href")

            # For now, don’t overthink parsing team/location; keep it simple.
            title = title_text
            team = None
            location = None

            posting = RawJobPosting(
                source=JobSource.OPENAI,
                title=title,
                location=location,
                team=team,
                apply_url=apply_url,
                detail_url=detail_url,
                raw_text=title_text,
                scraped_at=now,
            )
            results.append(posting)

        return results

    def fetch_jobs(self) -> List[RawJobPosting]:
        html = self.fetch_raw_html()
        return self.parse_listings(html)
