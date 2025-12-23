"""Enrich job postings by fetching job data via Ashby API/GraphQL instead of parsing HTML."""

import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Debug mode flag
DEBUG = os.getenv("JI_DEBUG") == "1"


def _url_hash(url: str) -> str:
    """Generate a hash for a URL to use as cache filename."""
    return hashlib.sha256(url.encode()).hexdigest()


def _get_html_cache_path(cache_dir: Path, url: str) -> Path:
    """Get the HTML cache file path for a URL."""
    return cache_dir / f"{_url_hash(url)}.html"


def _get_json_cache_path(cache_dir: Path, job_id: str) -> Path:
    """Get the JSON cache file path for a job ID."""
    return cache_dir / f"{job_id}.json"


def _fetch_html_cached(url: str, cache_dir: Path, use_cache: bool = True) -> Optional[str]:
    """
    Fetch HTML from URL with caching.

    Args:
        url: URL to fetch
        cache_dir: Directory to store cached HTML files
        use_cache: If True, check cache first; if False, always fetch

    Returns:
        HTML content, or None if fetch failed
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = _get_html_cache_path(cache_dir, url)

    # Check cache first
    if use_cache and cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    # Fetch from URL
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        
        # Validate response looks like HTML
        html = resp.text
        html_lower = html.lower()
        if "<html" not in html_lower and "<!doctype" not in html_lower:
            # Not HTML - print debugging info
            content_encoding = resp.headers.get("Content-Encoding", "not set")
            content_preview = resp.content[:80]
            print(f"  ⚠️  Response doesn't look like HTML for {url}")
            print(f"      Content-Encoding: {content_encoding}")
            print(f"      First 80 bytes: {content_preview}")
            return None
        
        # Save decoded text to cache
        cache_path.write_text(html, encoding="utf-8")
        return html
    except Exception as e:
        print(f"  ⚠️  Failed to fetch {url}: {e}")
        return None


def _extract_job_id_from_html(html: str) -> Optional[str]:
    """
    Extract job ID/posting ID from HTML by searching for embedded JSON.

    Searches for strings like "jobPostingId", "jobId", "postingId" in script tags.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Search all script tags for JSON containing job identifiers
    scripts = soup.find_all("script")
    for script in scripts:
        if not script.string:
            continue
        
        # Look for JSON-like content
        script_text = script.string.strip()
        if not (script_text.startswith("{") or script_text.startswith("[")):
            continue
        
        try:
            data = json.loads(script_text)
        except json.JSONDecodeError:
            # Try to find JSON-like patterns in the text
            for pattern in [
                r'"jobPostingId"\s*:\s*"([^"]+)"',
                r'"jobId"\s*:\s*"([^"]+)"',
                r'"postingId"\s*:\s*"([^"]+)"',
                r'"id"\s*:\s*"([a-f0-9-]{36})"',  # UUID pattern
            ]:
                match = re.search(pattern, script_text, re.IGNORECASE)
                if match:
                    job_id = match.group(1)
                    # Skip greenhouse and other non-ashby IDs
                    if "greenhouse" not in script_text.lower() and "ashby" in script_text.lower():
                        return job_id
            continue
        
        # Recursively search the JSON structure
        def find_job_id(obj: Any) -> Optional[str]:
            if isinstance(obj, dict):
                # Check for common job ID keys
                for key in ["jobPostingId", "jobId", "postingId", "id"]:
                    if key in obj:
                        value = obj[key]
                        if isinstance(value, str) and len(value) > 10:
                            # Basic validation: looks like an ID
                            if re.match(r'^[a-f0-9-]+$', value, re.IGNORECASE):
                                return value
                # Recurse
                for value in obj.values():
                    result = find_job_id(value)
                    if result:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = find_job_id(item)
                    if result:
                        return result
            return None
        
        job_id = find_job_id(data)
        if job_id:
            return job_id
    
    return None


def _extract_job_id_from_url(url: str) -> Optional[str]:
    """
    Extract job ID from URL path (UUID pattern).

    Example: https://jobs.ashbyhq.com/openai/0c22b805-3976-492e-81f2-7cf91f63a630/application
    """
    # Look for UUID pattern in URL
    uuid_pattern = r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
    match = re.search(uuid_pattern, url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _find_ashby_api_endpoint(html: str) -> Optional[str]:
    """Find the Ashby GraphQL API endpoint from HTML."""
    # Common Ashby API endpoints
    possible_endpoints = [
        "https://jobs.ashbyhq.com/api/non-user-graphql",
        "https://api.ashbyhq.com/non-user-graphql",
    ]
    
    # Check if endpoint is mentioned in HTML
    for endpoint in possible_endpoints:
        if endpoint in html:
            return endpoint
    
    # Default to most common endpoint
    return "https://jobs.ashbyhq.com/api/non-user-graphql"


def _fetch_job_data_from_api(job_id: str, api_endpoint: str, cache_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Fetch job data from Ashby GraphQL API.

    Args:
        job_id: Job posting ID
        api_endpoint: GraphQL API endpoint URL
        cache_dir: Directory to cache JSON responses

    Returns:
        Job data dict, or None if fetch failed
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    json_cache_path = _get_json_cache_path(cache_dir, job_id)
    
    # Check JSON cache first
    if json_cache_path.exists():
        try:
            return json.loads(json_cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception) as e:
            if DEBUG:
                print(f"      Failed to load cached JSON: {e}")
    
    # GraphQL query to fetch job posting details
    # This is a best-guess query structure based on common GraphQL patterns
    query = """
    query GetJobPosting($id: ID!) {
      jobPosting(id: $id) {
        id
        title
        location
        team {
          name
        }
        description
        responsibilities
        requirements
      }
    }
    """
    
    # Alternative simpler query if the above doesn't work
    simple_query = """
    query {
      jobPosting(id: "%s") {
        title
        location
        team
        description
      }
    }
    """ % job_id
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    # Try GraphQL POST request
    payloads = [
        {"query": query, "variables": {"id": job_id}},
        {"query": simple_query},
        {"jobPostingId": job_id},  # REST-style fallback
    ]
    
    for payload in payloads:
        try:
            resp = requests.post(
                api_endpoint,
                json=payload,
                headers=headers,
                timeout=20
            )
            resp.raise_for_status()
            
            data = resp.json()
            
            # Cache successful response
            json_cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            
            if DEBUG:
                print(f"      API endpoint: {api_endpoint}")
                print(f"      Top-level keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            
            return data
        except Exception as e:
            if DEBUG:
                print(f"      API request failed: {e}")
            continue
    
    return None


def _parse_job_data_from_json(api_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Parse job data from API JSON response.

    Returns dict with: title, location, team, jd_text
    """
    result = {
        "title": None,
        "location": None,
        "team": None,
        "jd_text": None,
    }
    
    # Recursively search for common fields
    def extract_field(obj: Any, field_names: List[str]) -> Optional[str]:
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = key.lower()
                if any(fn.lower() in key_lower for fn in field_names):
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                    elif isinstance(value, dict) and "name" in value:
                        return str(value["name"]).strip()
                # Recurse
                found = extract_field(value, field_names)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = extract_field(item, field_names)
                if found:
                    return found
        return None
    
    # Extract title
    result["title"] = extract_field(api_data, ["title", "name", "jobTitle"])
    
    # Extract location
    result["location"] = extract_field(api_data, ["location", "city", "office"])
    
    # Extract team
    team = extract_field(api_data, ["team", "department", "group"])
    if team:
        result["team"] = team
    
    # Extract job description (combine description, responsibilities, requirements)
    jd_parts = []
    for field in ["description", "responsibilities", "requirements", "jobDescription", "fullDescription"]:
        text = extract_field(api_data, [field])
        if text and len(text) > 50:
            jd_parts.append(text)
    
    if jd_parts:
        result["jd_text"] = "\n\n".join(jd_parts)
    
    return result


def _extract_from_ld_json(soup: BeautifulSoup) -> Optional[str]:
    """Extract job description from script[type="application/ld+json"]."""
    ld_scripts = soup.find_all("script", type="application/ld+json")
    for script in ld_scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0] if data else {}
            if isinstance(data, dict) and "description" in data:
                desc = data["description"]
                if desc and isinstance(desc, str) and len(desc.strip()) > 50:
                    return desc.strip()
        except (json.JSONDecodeError, AttributeError, IndexError):
            continue
    return None


def _extract_from_next_data(soup: BeautifulSoup) -> Optional[str]:
    """Extract job description from script[id="__NEXT_DATA__"]."""
    next_data_script = soup.find("script", id="__NEXT_DATA__")
    if not next_data_script or not next_data_script.string:
        return None

    try:
        data = json.loads(next_data_script.string)
    except json.JSONDecodeError:
        return None

    def find_description(obj: Any) -> Optional[str]:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower() in ("description", "jobdescription", "job_description"):
                    if isinstance(value, str) and len(value.strip()) > 50:
                        return value.strip()
                result = find_description(value)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = find_description(item)
                if result:
                    return result
        return None

    return find_description(data)


def _extract_from_visible_text(soup: BeautifulSoup) -> Optional[str]:
    """Extract visible text from main content container as fallback."""
    selectors = [
        "main",
        "[role='main']",
        ".job-description",
        ".job-details",
        ".content",
        "#content",
        "[class*='description']",
        "[class*='detail']",
    ]

    for selector in selectors:
        container = soup.select_one(selector)
        if container:
            for tag in container.find_all(["script", "style"]):
                tag.decompose()
            text = container.get_text(separator="\n", strip=True)
            if text and len(text.strip()) > 100:
                return text.strip()

    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    if text and len(text.strip()) > 100:
        return text.strip()

    return None


def extract_jd_text_from_html(html: str) -> Optional[str]:
    """Extract job description text from HTML (fallback method)."""
    soup = BeautifulSoup(html, "html.parser")

    jd = _extract_from_ld_json(soup)
    if jd:
        return jd

    jd = _extract_from_next_data(soup)
    if jd:
        return jd

    jd = _extract_from_visible_text(soup)
    return jd


def extract_clean_title_from_html(html: str) -> Optional[str]:
    """Extract clean job title from HTML (fallback method)."""
    soup = BeautifulSoup(html, "html.parser")

    # JSON-LD title/name
    ld_scripts = soup.find_all("script", type="application/ld+json")
    for script in ld_scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0] if data else {}
            if isinstance(data, dict):
                for field in ["title", "name"]:
                    if field in data:
                        title = data[field]
                        if title and isinstance(title, str) and title.strip():
                            return title.strip()
        except (json.JSONDecodeError, AttributeError, IndexError):
            continue

    # <h1> tag
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        if title:
            return title

    return None


def enrich_jobs(
    labeled_jobs: List[Dict[str, Any]],
    cache_dir: Path,
    rate_limit: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Enrich labeled jobs by fetching job data via Ashby API, falling back to HTML parsing.

    Args:
        labeled_jobs: List of job dicts with at least: title, apply_url, location, team, relevance
        cache_dir: Directory to cache fetched HTML and JSON
        rate_limit: Seconds to wait between uncached fetches

    Returns:
        List of enriched job dicts with added jd_text and fetched_at fields
    """
    enriched = []
    fetched_count = 0

    for i, job in enumerate(labeled_jobs, 1):
        apply_url = job.get("apply_url", "")
        if not apply_url:
            print(f"  [{i}/{len(labeled_jobs)}] Skipping {job.get('title', 'Unknown')} - no apply_url")
            enriched.append({**job, "jd_text": None, "fetched_at": None})
            continue

        print(f"  [{i}/{len(labeled_jobs)}] Processing: {job.get('title', 'Unknown')}")

        # Check if we need to fetch (not in cache)
        html_cache_path = _get_html_cache_path(cache_dir, apply_url)
        is_cached = html_cache_path.exists()

        # Fetch HTML (for job ID extraction and fallback)
        html = _fetch_html_cached(apply_url, cache_dir, use_cache=True)
        if not html:
            print(f"    ❌ Failed to fetch HTML")
            enriched.append({**job, "jd_text": None, "fetched_at": None})
            continue

        # Try API-based enrichment first
        job_id = _extract_job_id_from_html(html)
        if not job_id:
            job_id = _extract_job_id_from_url(apply_url)
        
        api_data = None
        if job_id:
            api_endpoint = _find_ashby_api_endpoint(html)
            api_data = _fetch_job_data_from_api(job_id, api_endpoint, cache_dir)
        
        if api_data:
            # Parse data from API JSON
            parsed_data = _parse_job_data_from_json(api_data)
            
            clean_title = parsed_data["title"] or job.get("title")
            location = parsed_data["location"] or job.get("location")
            team = parsed_data["team"] or job.get("team")
            jd_text = parsed_data["jd_text"]
            
            if jd_text:
                print(f"    ✅ Extracted via API: {len(jd_text)} chars")
            else:
                print(f"    ⚠️  API response missing JD text, falling back to HTML")
                jd_text = extract_jd_text_from_html(html)
                if not clean_title:
                    clean_title = extract_clean_title_from_html(html) or job.get("title")
        else:
            # Fall back to HTML parsing
            print(f"    ⚠️  API fetch failed, using HTML parsing")
            clean_title = extract_clean_title_from_html(html) or job.get("title")
            location = job.get("location")
            team = job.get("team")
            jd_text = extract_jd_text_from_html(html)
        
        fetched_at = datetime.utcnow().isoformat()

        if jd_text:
            print(f"    ✅ Extracted {len(jd_text)} chars")
        else:
            print(f"    ⚠️  No JD text extracted")

        enriched.append({
            **job,
            "title": clean_title,
            "location": location,
            "team": team,
            "jd_text": jd_text,
            "fetched_at": fetched_at,
        })

        # Rate limiting for uncached fetches
        if not is_cached:
            fetched_count += 1
            if i < len(labeled_jobs):
                time.sleep(rate_limit)

    return enriched
