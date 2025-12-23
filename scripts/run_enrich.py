#!/usr/bin/env python

"""
Entry point to run the job enrichment pipeline.

Usage (from repo root, with venv active):

    python scripts/run_enrich.py
"""

import json
import sys
from pathlib import Path

# Add <repo_root>/src to sys.path so `import ji_engine` works
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ji_engine.pipeline.enrichment import enrich_jobs  # noqa: E402


def main() -> None:
    """Load labeled jobs, enrich them, and save results."""
    # Load labeled jobs
    labeled_path = ROOT / "data" / "openai_labeled_jobs.json"
    if not labeled_path.exists():
        print(f"Error: Labeled jobs file not found: {labeled_path}")
        print("Run scripts/run_classify.py first to generate labeled jobs.")
        sys.exit(1)

    with open(labeled_path, "r", encoding="utf-8") as f:
        labeled_jobs = json.load(f)

    # Filter for RELEVANT and MAYBE
    filtered_jobs = [
        job for job in labeled_jobs
        if job.get("relevance") in {"RELEVANT", "MAYBE"}
    ]

    print(f"Loaded {len(labeled_jobs)} labeled jobs")
    print(f"Filtering for RELEVANT/MAYBE: {len(filtered_jobs)} jobs to enrich\n")

    if not filtered_jobs:
        print("No jobs to enrich. Exiting.")
        return

    # Enrich jobs
    cache_dir = ROOT / "data" / "ashby_cache"
    enriched_jobs = enrich_jobs(filtered_jobs, cache_dir, rate_limit=1.0)

    # Count successes and failures
    successful = sum(1 for job in enriched_jobs if job.get("jd_text"))
    failed = len(enriched_jobs) - successful

    # Save enriched jobs
    output_path = ROOT / "data" / "openai_enriched_jobs.json"
    output_data = [
        {
            "title": job.get("title"),
            "apply_url": job.get("apply_url"),
            "location": job.get("location"),
            "team": job.get("team"),
            "relevance": job.get("relevance"),
            "jd_text": job.get("jd_text"),
            "fetched_at": job.get("fetched_at"),
        }
        for job in enriched_jobs
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*60}")
    print("Enrichment Summary:")
    print(f"  Total processed: {len(enriched_jobs)}")
    print(f"  Successfully enriched: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Output: {output_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
