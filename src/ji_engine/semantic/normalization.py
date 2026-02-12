from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .core import SEMANTIC_NORM_VERSION, normalize_text_for_embedding


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def compose_job_text_semantic_norm_v1(job: Mapping[str, Any]) -> str:
    """Build deterministic semantic text from ordered, labeled job fields."""
    fields = [
        ("title", _first_non_empty(job.get("title"))),
        ("location", _first_non_empty(job.get("location"), job.get("locationName"))),
        ("team", _first_non_empty(job.get("team"), job.get("department"), job.get("departmentName"))),
        ("summary", _first_non_empty(job.get("summary"))),
        ("description", _first_non_empty(job.get("description"), job.get("jd_text"), job.get("raw_text"))),
    ]
    labeled = [f"{name}:{value}" for name, value in fields if value]
    return " | ".join(labeled)


def normalize_job_text_semantic_norm_v1(job: Mapping[str, Any]) -> str:
    return normalize_text_for_embedding(compose_job_text_semantic_norm_v1(job))


def normalize_profile_text_semantic_norm_v1(profile_payload: Any) -> str:
    canonical = json.dumps(profile_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return normalize_text_for_embedding(canonical)


def semantic_content_hash_v1(normalized_text: str, *, norm_version: str = SEMANTIC_NORM_VERSION) -> str:
    payload = f"{norm_version}\n{normalized_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
