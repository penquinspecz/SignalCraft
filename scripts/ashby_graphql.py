# scripts/ashby_graphql.py
from __future__ import annotations
import json
import time
from pathlib import Path
import requests

API_URL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting"

QUERY = """
query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) {
  jobPosting(
    organizationHostedJobsPageName: $organizationHostedJobsPageName
    jobPostingId: $jobPostingId
  ) {
    id
    title
    departmentName
    departmentExternalName
    locationName
    workplaceType
    employmentType
    teamNames
    descriptionHtml
    secondaryLocationNames
  }
}
"""

def fetch_job_posting(org: str, job_id: str, cache_dir: Path, *, force: bool = False) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{job_id}.json"
    if cache_path.exists() and not force:
        return json.loads(cache_path.read_text(encoding="utf-8"))

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0",
        "referer": f"https://jobs.ashbyhq.com/{org}/{job_id}/application",
        "origin": "https://jobs.ashbyhq.com",
        "accept-encoding": "gzip, deflate, br",
        "apollographql-client-name": "frontend_non_user",
        "apollographql-client-version": "0.1.0",
    }

    payload = {
        "operationName": "ApiJobPosting",
        "variables": {"organizationHostedJobsPageName": org, "jobPostingId": job_id},
        "query": QUERY,
    }

    # light retry for transient CDN hiccups / 429s
    for attempt in range(4):
        r = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()

    r.raise_for_status()
    raise RuntimeError("Unreachable")
