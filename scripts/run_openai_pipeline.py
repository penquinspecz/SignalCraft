#!/usr/bin/env python3
"""
Run OpenAI pipeline end-to-end:
1) scrape (snapshot)
2) parse + classify (existing run scripts)
3) enrich (Ashby GraphQL)
4) score (CS-fit ranking)

Assumes existing scripts:
- scripts/run_scrape.py
- scripts/run_classify.py
- scripts/enrich_jobs.py
- scripts/score_jobs.py
"""

from __future__ import annotations
import subprocess
import sys

def run(cmd: list[str]) -> None:
    print("\n$ " + " ".join(cmd))
    subprocess.check_call(cmd)

def main() -> int:
    # Use the venv python to ensure deps resolve
    py = sys.executable

    run([py, "scripts/run_scrape.py"])
    run([py, "scripts/run_classify.py"])
    run([py, "-m", "scripts.enrich_jobs"])
    run([py, "scripts/score_jobs.py"])

    print("\n✅ Pipeline complete.")
    print("Outputs:")
    print(" - data/openai_enriched_jobs.json")
    print(" - data/openai_ranked_jobs.json")
    print(" - data/openai_ranked_jobs.csv")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
