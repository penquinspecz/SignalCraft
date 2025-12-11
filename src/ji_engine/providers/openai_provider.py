from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from ji_engine.models import RawJobPosting, JobSource
from ji_engine.providers.base import BaseJobProvider


CAREERS_SEARCH_URL = "https://openai.com/careers/search/"
SNAPSHOT_DIR = Path("data") / "openai_snapshots"
SNAPSHOT_FILE = SNAPSHOT_DIR / "index.html"


class OpenAICareersProvider(BaseJobProvider):
    """
    Provider for OpenAI careers.

    For now we prioritize SNAPSHOT mode because the live site returns 403
    to our requests client. Live scraping is a best-effort bonus.

    In SNAPSHOT mode, we expect:
        data/openai_snapshots/index.html
    to be a page you manually saved from your browser.
    """

    def scrape_live(self) -> List[RawJobPosting]:
        """
        Attempt a live HTTP scrape.

        This will likely hit 403 due to WAF. We keep it simple and let the
        BaseJobProvider handle fallback to snapshot.
        """
        headers = {
            "User-Agent": "job-intelligence-engine/0.1 (+personal project)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(CAREERS_SEARCH_URL, headers=headers, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Live scrape failed with status {resp.status_code} at {CAREERS_SEARCH_URL}"
            )
        html = resp.text
        return self._parse_html(html)

    def load_from_snapshot(self) -> List[RawJobPosting]:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

        if not SNAPSHOT_FILE.exists():
            print(f"[OpenAICareersProvider] ❌ Snapshot not found at {SNAPSHOT_FILE}")
            print(
                "Save https://openai.com/careers/search/ as 'index.html' in "
                "data/openai_snapshots/ and rerun."
            )
            return []

        print(f"[OpenAICareersProvider] 📂 Using snapshot {SNAPSHOT_FILE}")
        html = SNAPSHOT_FILE.read_text(encoding="utf-8")
        return self._parse_html(html)

    def _parse_html(self, html: str) -> List[RawJobPosting]:
        """
        Parse the saved careers page HTML and extract job postings.

        This is intentionally heuristic and may need adjustment once we
        inspect the actual snapshot structure.
        """
        soup = BeautifulSoup(html, "html.parser")
        results: List[RawJobPosting] = []
        now = datetime.utcnow()

        # Initial heuristic: look for <a> tags with Ashby job links
        apply_links = soup.find_all("a", href=lambda h: h and "jobs.ashbyhq.com" in h)

        for apply_tag in apply_links:
            apply_url = apply_tag.get("href")

            # Try to find nearby text as the title.
            title_tag = apply_tag.find_previous("a")
            if not title_tag or title_tag is apply_tag:
                title_text = apply_tag.get_text(strip=True)
                detail_url: Optional[str] = apply_url
            else:
                title_text = title_tag.get_text(strip=True)
                detail_url = title_tag.get("href")

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

        print(f"[OpenAICareersProvider] Parsed {len(results)} jobs from HTML")
        return results
