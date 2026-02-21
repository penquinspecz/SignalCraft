"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ji_engine.ai.accounting import estimate_cost_usd, estimate_tokens, resolve_model_rates
from ji_engine.config import DEFAULT_CANDIDATE_ID, REPO_ROOT, RUN_METADATA_DIR, STATE_DIR
from ji_engine.run_repository import FileSystemRunRepository, RunRepository
from ji_engine.utils.content_fingerprint import content_fingerprint
from ji_engine.utils.job_identity import job_identity
from ji_engine.utils.time import utc_now_iso

try:
    from scripts.schema_validate import resolve_named_schema_path, validate_payload
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from schema_validate import resolve_named_schema_path, validate_payload  # type: ignore

logger = logging.getLogger(__name__)

PROMPT_VERSION = "job_briefs_v1"
PROMPT_PATH = REPO_ROOT / "docs" / "prompts" / "job_briefs_v1.md"
JOB_BRIEF_SCHEMA_VERSION = 1
_JOB_BRIEF_SCHEMA_CACHE: Optional[Dict[str, Any]] = None


def _run_dir(run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path:
    return _run_repository().resolve_run_dir(run_id, candidate_id=candidate_id)


def _run_repository() -> RunRepository:
    return FileSystemRunRepository(RUN_METADATA_DIR)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return _sha256_bytes(path.read_bytes())


def _job_brief_schema() -> Dict[str, Any]:
    global _JOB_BRIEF_SCHEMA_CACHE
    if _JOB_BRIEF_SCHEMA_CACHE is None:
        schema_path = resolve_named_schema_path("ai_job_brief", JOB_BRIEF_SCHEMA_VERSION)
        _JOB_BRIEF_SCHEMA_CACHE = json.loads(schema_path.read_text(encoding="utf-8"))
    return _JOB_BRIEF_SCHEMA_CACHE


def _load_prompt(path: Path) -> Tuple[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    text = path.read_text(encoding="utf-8")
    return text, _sha256_bytes(text.encode("utf-8"))


def _load_ranked(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if isinstance(data, list):
        return data
    return []


def _profile_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return _sha256_bytes(path.read_bytes())


def _job_id(job: Dict[str, Any]) -> str:
    return str(job.get("job_id") or job.get("apply_url") or job_identity(job))


def _job_hash(job: Dict[str, Any]) -> str:
    jd = job.get("jd_text") or ""
    if isinstance(jd, str) and jd:
        return _sha256_bytes(jd.encode("utf-8"))
    return content_fingerprint(job)


def _token_estimate(text: str) -> int:
    return estimate_tokens(text)


def _brief_cache_dir(profile: str) -> Path:
    return STATE_DIR / "ai_job_briefs_cache" / profile


def _cache_key(job: Dict[str, Any], profile_hash: str, model: str) -> str:
    del model
    parts = [_job_hash(job), profile_hash, PROMPT_VERSION]
    return _sha256_bytes("|".join(parts).encode("utf-8"))


def _load_cache(profile: str, key: str) -> Optional[Dict[str, Any]]:
    path = _brief_cache_dir(profile) / f"{key}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _save_cache(profile: str, key: str, payload: Dict[str, Any]) -> None:
    path = _brief_cache_dir(profile) / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fit_bullets(job: Dict[str, Any]) -> List[str]:
    bullets = []
    role_band = job.get("role_band") or ""
    if role_band:
        bullets.append(f"Role band aligns with {role_band}.")
    for sig in (job.get("fit_signals") or [])[:4]:
        bullets.append(f"Evidence of {sig.replace('fit:', '').replace('_', ' ')}.")
    return bullets[:5] or ["Matches core responsibilities in the role description."]


def _gap_bullets(job: Dict[str, Any]) -> List[str]:
    bullets = []
    for sig in (job.get("risk_signals") or [])[:3]:
        bullets.append(f"Address risk area: {sig.replace('risk:', '').replace('_', ' ')}.")
    if not bullets:
        bullets.append("No major gaps flagged; verify role-specific tooling and domain expertise.")
    return bullets


def _interview_focus(job: Dict[str, Any]) -> List[str]:
    bullets = []
    for sig in (job.get("fit_signals") or [])[:3]:
        bullets.append(f"Prepare impact story on {sig.replace('fit:', '').replace('_', ' ')}.")
    bullets.append("Be ready to quantify customer outcomes and adoption metrics.")
    return bullets[:5]


def _resume_tweaks(job: Dict[str, Any]) -> List[str]:
    title = job.get("title") or "the role"
    bullets = [
        f"Mirror {title} keywords in summary and recent role bullets.",
        "Highlight deployment/implementation outcomes with concrete metrics.",
        "Show cross-functional leadership and customer-facing delivery.",
    ]
    return bullets[:5]


def _brief_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": _job_id(job),
        "apply_url": job.get("apply_url") or "",
        "title": job.get("title") or "Untitled",
        "score": int(job.get("score", 0) or 0),
        "why_fit": _fit_bullets(job),
        "gaps": _gap_bullets(job),
        "interview_focus": _interview_focus(job),
        "resume_tweaks": _resume_tweaks(job),
    }


def _validate_brief_payload(brief: Dict[str, Any]) -> List[str]:
    return validate_payload(brief, _job_brief_schema())


def _write_error_artifact(*, run_dir: Path, profile: str, payload: Dict[str, Any]) -> Path:
    path = run_dir / f"ai_job_briefs.{profile}.error.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def generate_job_briefs(
    *,
    provider: str,
    profile: str,
    ranked_path: Path,
    run_id: str,
    max_jobs: int,
    max_tokens_per_job: int,
    total_budget: int,
    ai_enabled: bool,
    ai_reason: str,
    model_name: str,
    prompt_path: Path = PROMPT_PATH,
    profile_path: Path = Path("data/candidate_profile.json"),
    candidate_id: str = DEFAULT_CANDIDATE_ID,
) -> Tuple[Path, Path, Dict[str, Any]]:
    prompt_text, prompt_sha = _load_prompt(prompt_path)
    prompt_text = prompt_text.strip()

    ranked = _load_ranked(ranked_path)
    top_jobs = ranked[: max(0, max_jobs)]
    profile_hash = _profile_hash(profile_path)

    metadata = {
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha,
        "model": model_name,
        "provider": provider,
        "profile": profile,
        "timestamp": utc_now_iso(),
        "input_hashes": {"ranked": _sha256_path(ranked_path), "profile": profile_hash},
        "max_jobs": max_jobs,
        "max_tokens_per_job": max_tokens_per_job,
        "total_budget": total_budget,
    }
    rates = resolve_model_rates(model_name)

    run_dir = _run_dir(run_id, candidate_id=candidate_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / f"ai_job_briefs.{profile}.json"
    md_path = run_dir / f"ai_job_briefs.{profile}.md"

    briefs: List[Dict[str, Any]] = []
    cache_hits = 0
    used_tokens = 0
    skipped_budget = 0
    schema_errors: List[str] = []
    invalid_job_id: Optional[str] = None

    for job in top_jobs:
        jd_text = job.get("jd_text") or ""
        estimated_tokens = _token_estimate(jd_text if isinstance(jd_text, str) else "")
        if estimated_tokens > max_tokens_per_job:
            estimated_tokens = max_tokens_per_job
        if used_tokens + estimated_tokens > total_budget:
            skipped_budget += 1
            continue

        key = _cache_key(job, profile_hash, model_name)
        cached = _load_cache(profile, key)
        if cached:
            cached_errors = _validate_brief_payload(cached)
            if cached_errors:
                schema_errors = [f"job_id={_job_id(job)}: " + "; ".join(cached_errors)]
                invalid_job_id = _job_id(job)
                break
            cache_hits += 1
            briefs.append(cached)
            continue

        if ai_enabled:
            brief = _brief_payload(job)
        else:
            brief = _brief_payload(job)
            brief["why_fit"] = []
            brief["gaps"] = []
            brief["interview_focus"] = []
            brief["resume_tweaks"] = []

        brief_errors = _validate_brief_payload(brief)
        if brief_errors:
            schema_errors = [f"job_id={_job_id(job)}: " + "; ".join(brief_errors)]
            invalid_job_id = _job_id(job)
            break

        _save_cache(profile, key, brief)
        briefs.append(brief)
        used_tokens += estimated_tokens

    status = "ok" if ai_enabled else "disabled"
    tokens_in = used_tokens if ai_enabled else 0
    rendered = json.dumps(briefs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    tokens_out = estimate_tokens(rendered) if ai_enabled else 0
    ai_accounting = {
        "model": model_name,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "input_per_1k_usd": rates["input_per_1k"],
        "output_per_1k_usd": rates["output_per_1k"],
        "estimated_cost_usd": estimate_cost_usd(
            tokens_in,
            tokens_out,
            input_per_1k=rates["input_per_1k"],
            output_per_1k=rates["output_per_1k"],
        ),
    }
    payload = {
        "status": status,
        "reason": "" if ai_enabled else ai_reason,
        "provider": provider,
        "profile": profile,
        "briefs": briefs,
        "metadata": {
            **metadata,
            "cache_hits": cache_hits,
            "estimated_tokens_used": used_tokens,
            "skipped_due_to_budget": skipped_budget,
            "ai_accounting": ai_accounting,
        },
    }
    if schema_errors:
        status = "error"
        reason = "job_brief_schema_validation_failed"
        error_payload = {
            "error": reason,
            "run_id": run_id,
            "candidate_id": candidate_id,
            "provider": provider,
            "profile": profile,
            "invalid_job_id": invalid_job_id,
            "schema_errors": schema_errors,
            "generated_at": utc_now_iso(),
            "schema": "ai_job_brief.v1",
        }
        error_path = _write_error_artifact(run_dir=run_dir, profile=profile, payload=error_payload)
        payload = {
            "status": status,
            "reason": reason,
            "provider": provider,
            "profile": profile,
            "briefs": [],
            "metadata": {
                **metadata,
                "cache_hits": cache_hits,
                "estimated_tokens_used": used_tokens,
                "skipped_due_to_budget": skipped_budget,
                "ai_accounting": ai_accounting,
                "error_artifact": str(error_path),
                "schema_errors": schema_errors,
                "invalid_job_id": invalid_job_id,
            },
        }

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_briefs_markdown(payload), encoding="utf-8")
    return md_path, json_path, payload


def _briefs_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# AI Job Briefs",
        "",
        f"Provider: **{payload.get('provider')}**",
        f"Profile: **{payload.get('profile')}**",
        f"Status: **{payload.get('status')}**",
        "",
    ]
    if payload.get("status") != "ok":
        lines.append(f"Reason: {payload.get('reason')}")
        lines.append("")

    for brief in payload.get("briefs") or []:
        lines.append(f"## {brief.get('title')} — {brief.get('score')}")
        if brief.get("apply_url"):
            lines.append(f"[Apply link]({brief.get('apply_url')})")
        lines.append("")
        lines.append("**Why fit**")
        for item in brief.get("why_fit") or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("**Gaps**")
        for item in brief.get("gaps") or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("**Interview focus**")
        for item in brief.get("interview_focus") or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("**Resume tweaks**")
        for item in brief.get("resume_tweaks") or []:
            lines.append(f"- {item}")
        lines.append("")

    meta = payload.get("metadata") or {}
    lines.append("## Metadata")
    for key in sorted(meta.keys()):
        lines.append(f"- {key}: {meta[key]}")
    lines.append("")
    return "\n".join(lines)
