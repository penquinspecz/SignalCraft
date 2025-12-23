# scripts/enrich_jobs.py
import json
from pathlib import Path
from ashby_graphql import fetch_job_posting
from html_to_text import html_to_text

ORG = "openai"
CACHE_DIR = Path("data/ashby_cache_json")
IN_PATH = Path("data/jobs_classified.json")      # <-- adjust to your actual file
OUT_PATH = Path("data/jobs_enriched.json")

def main():
    jobs = json.loads(IN_PATH.read_text(encoding="utf-8"))
    out = []

    for j in jobs:
        rel = j.get("relevance")
        url = j.get("apply_url") or ""
        # expect https://jobs.ashbyhq.com/openai/<uuid>/application
        job_id = url.split("/openai/")[-1].split("/")[0] if "/openai/" in url else None

        if rel in ("RELEVANT", "MAYBE") and job_id:
            data = fetch_job_posting(ORG, job_id, CACHE_DIR)
            jp = (data.get("data") or {}).get("jobPosting") or {}
            desc_html = jp.get("descriptionHtml") or ""
            j["title"] = jp.get("title") or j.get("title")
            j["location"] = jp.get("locationName")
            j["team"] = jp.get("teamNames")
            j["department"] = jp.get("departmentName")
            j["jd_text"] = html_to_text(desc_html)

        out.append(j)

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(out)} jobs -> {OUT_PATH}")

if __name__ == "__main__":
    main()
