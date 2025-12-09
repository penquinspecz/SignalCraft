#!/usr/bin/env python

"""
Entry point to run the raw scraping pipeline.

Usage (from repo root, with venv active):

    python scripts/run_scrape.py
"""

import sys
from pathlib import Path

# Add <repo_root>/src to sys.path so `import ji_engine` works
ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ji_engine.scraper import ScraperManager  # noqa: E402

def main() -> None:
    manager = ScraperManager(output_dir="data")
    manager.run_all()


if __name__ == "__main__":
    main()


