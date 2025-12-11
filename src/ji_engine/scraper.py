from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ji_engine.models import RawJobPosting
from ji_engine.providers.openai_provider import OpenAICareersProvider


class ScraperManager:
    """
    Coordinates scraping from one or more providers.
    For Sprint 1, we only wire up OpenAI.
    """

    def __init__(self, output_dir: str = "data"):
        self.output_path = Path(output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)

    def scrape_openai(self, mode: str = "SNAPSHOT") -> List[RawJobPosting]:
        provider = OpenAICareersProvider(mode=mode, data_dir="data")
        jobs = provider.fetch_jobs()
        return jobs

    def run_all(self, mode: str = "SNAPSHOT") -> None:
        all_jobs: List[RawJobPosting] = []

        openai_jobs = self.scrape_openai(mode=mode)
        all_jobs.extend(openai_jobs)

        output_file = self.output_path / "openai_raw_jobs.json"
        payload = [job.to_dict() for job in all_jobs]

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"Scraped {len(all_jobs)} jobs.")
        print(f"Wrote JSON to {output_file.resolve()}")
