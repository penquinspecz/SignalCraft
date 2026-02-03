from __future__ import annotations

import hashlib
import json
from typing import Dict, Literal, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_DROP_QUERY_PREFIXES = ("utm_", "gh_", "lever_")
_DROP_QUERY_KEYS = {
    "gh_jid",
    "gh_src",
    "gh_source",
    "lever-source",
    "lever_source",
    "source",
    "sourceid",
    "ref",
    "referrer",
    "icid",
    "mc_cid",
    "mc_eid",
}


def normalize_job_text(value: str, *, casefold: bool = True) -> str:
    normalized = " ".join(value.split()).strip()
    return normalized.casefold() if casefold else normalized


def _should_drop_param(key: str) -> bool:
    lowered = key.casefold()
    if lowered in _DROP_QUERY_KEYS:
        return True
    return any(lowered.startswith(prefix) for prefix in _DROP_QUERY_PREFIXES)


def normalize_job_url(value: str) -> str:
    normalized = normalize_job_text(value, casefold=False)
    if not normalized:
        return ""
    parts = urlsplit(normalized)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    filtered = [(key, val) for key, val in query_pairs if key and not _should_drop_param(key)]
    filtered.sort(key=lambda item: (item[0].casefold(), item[1]))
    query = urlencode(filtered, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def job_identity(job: Dict[str, object], *, mode: Literal["legacy", "provider"] = "legacy") -> str:
    """
    Stable identifier for job postings.

    Preference:
    Legacy mode (default):
    1. job_id
    2. apply_url
    3. detail_url
    4. content hash (title/location/team/description)

    Provider mode:
    1. provider + job_id (if provider present)
    2. job_id
    3. hash(apply_url + title)
    4. hash(detail_url + title)
    5. content hash (title/location/team/description)
    """

    def _normalize(value: str, *, lower: bool = False) -> str:
        normalized = normalize_job_text(value, casefold=False)
        return normalized.casefold() if lower else normalized

    job_id = job.get("job_id")
    if isinstance(job_id, str):
        normalized = _normalize(job_id, lower=True)
        if normalized:
            if mode == "provider":
                provider = job.get("provider") or job.get("source") or ""
                provider_norm = _normalize(str(provider), lower=True) if provider else ""
                return f"{provider_norm}:{normalized}" if provider_norm else normalized
            return normalized

    if mode == "provider":
        provider = job.get("provider") or job.get("source") or ""
        provider_norm = _normalize(str(provider), lower=True) if provider else ""
        title_norm = _normalize(str(job.get("title") or ""), lower=True)

        def _hash_url_field(value: Optional[str], field: str) -> Optional[str]:
            if not isinstance(value, str):
                return None
            normalized_url = normalize_job_url(value)
            if not normalized_url:
                return None
            payload = {"provider": provider_norm, field: normalized_url, "title": title_norm}
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

        apply_hash = _hash_url_field(job.get("apply_url"), "apply_url")
        if apply_hash:
            return apply_hash
        detail_hash = _hash_url_field(job.get("detail_url"), "detail_url")
        if detail_hash:
            return detail_hash

    for field in ("apply_url", "detail_url"):
        value = job.get(field)
        if isinstance(value, str):
            normalized = normalize_job_url(value)
            if normalized:
                return normalized

    description = (
        job.get("description_text") or job.get("jd_text") or job.get("description") or job.get("descriptionHtml") or ""
    )
    payload = {
        "title": _normalize(str(job.get("title") or ""), lower=True),
        "location": _normalize(str(job.get("location") or job.get("locationName") or ""), lower=True),
        "team": _normalize(str(job.get("team") or job.get("department") or ""), lower=True),
        "description": _normalize(str(description), lower=True),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
