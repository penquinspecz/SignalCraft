"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ji_engine.ai.accounting import estimate_cost_usd, estimate_tokens, resolve_model_rates
from ji_engine.ai.insights_input import build_weekly_insights_input
from ji_engine.config import DEFAULT_CANDIDATE_ID, REPO_ROOT, RUN_METADATA_DIR
from ji_engine.run_repository import FileSystemRunRepository, RunRepository
from ji_engine.utils.time import utc_now_iso

try:
    from scripts.schema_validate import resolve_named_schema_path, validate_payload
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from schema_validate import resolve_named_schema_path, validate_payload  # type: ignore

logger = logging.getLogger(__name__)

PROMPT_VERSION = "weekly_insights_v4"
PROMPT_PATH = REPO_ROOT / "docs" / "prompts" / "weekly_insights_v4.md"
_OUTPUT_SCHEMA_VERSION = 1
_OUTPUT_SCHEMA_CACHE: Optional[Dict[str, Any]] = None
_ALLOWED_EVIDENCE_FIELDS = frozenset(
    {
        "job_counts",
        "top_companies",
        "top_titles",
        "top_locations",
        "top_skills",
        "scoring_summary",
        "trend_analysis",
        "company_growth",
        "title_growth",
        "location_shift",
        "most_common_penalties",
        "strongest_positive_signals",
        "strongest_negative_signals",
        "score_distribution",
        "top_families",
        "diffs",
    }
)


def _run_dir(run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path:
    return _run_repository().resolve_run_dir(run_id, candidate_id=candidate_id)


def _run_repository() -> RunRepository:
    return FileSystemRunRepository(RUN_METADATA_DIR)


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _load_prompt(path: Path) -> Tuple[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    text = path.read_text(encoding="utf-8")
    return text, _sha256_bytes(text.encode("utf-8"))


def _output_schema() -> Dict[str, Any]:
    global _OUTPUT_SCHEMA_CACHE
    if _OUTPUT_SCHEMA_CACHE is None:
        schema_path = resolve_named_schema_path("ai_insights_output", _OUTPUT_SCHEMA_VERSION)
        _OUTPUT_SCHEMA_CACHE = json.loads(schema_path.read_text(encoding="utf-8"))
    return _OUTPUT_SCHEMA_CACHE


def _window_payload(insights_input: Dict[str, Any], days: int) -> Dict[str, Any]:
    windows = (
        ((insights_input.get("trend_analysis") or {}).get("windows") or []) if isinstance(insights_input, dict) else []
    )
    if not isinstance(windows, list):
        return {}
    for item in windows:
        if isinstance(item, dict) and int(item.get("window_days", 0) or 0) == days:
            return item
    return {}


def _build_top_actions(insights_input: Dict[str, Any], *, status: str) -> List[Dict[str, Any]]:
    counts = insights_input.get("job_counts") if isinstance(insights_input.get("job_counts"), dict) else {}
    window_7 = _window_payload(insights_input, 7)
    window_30 = _window_payload(insights_input, 30)
    actions: List[Dict[str, Any]] = [
        {
            "title": "Prioritize highest-velocity titles",
            "rationale": (f"{int(counts.get('new', 0) or 0)} new roles detected; focus on top title clusters first."),
            "supporting_evidence_fields": ["job_counts", "top_titles", "trend_analysis"],
        },
        {
            "title": "Rebalance company outreach",
            "rationale": "Recent company concentration changed; shift outreach to growing employers.",
            "supporting_evidence_fields": ["top_companies", "company_growth", "trend_analysis"],
        },
        {
            "title": "Adjust location targeting",
            "rationale": "Location distribution shifted over recent windows; align search filters accordingly.",
            "supporting_evidence_fields": ["top_locations", "location_shift", "trend_analysis"],
        },
        {
            "title": "Tune threshold for conversion",
            "rationale": "Score distribution and summary stats indicate where shortlist cutoffs should move.",
            "supporting_evidence_fields": ["scoring_summary", "score_distribution", "diffs"],
        },
        {
            "title": "Mitigate recurring penalties",
            "rationale": "Recurring negative signals can be countered with targeted profile positioning updates.",
            "supporting_evidence_fields": [
                "most_common_penalties",
                "strongest_negative_signals",
                "strongest_positive_signals",
            ],
        },
    ]

    # Deterministically specialize rationale text by status and windows without altering action order.
    if status != "ok":
        actions[0]["rationale"] = (
            "AI generation disabled or unavailable; use structured trends to prioritize top titles."
        )
    else:
        runs_7 = int(window_7.get("runs_considered", 0) or 0) if isinstance(window_7, dict) else 0
        runs_30 = int(window_30.get("runs_considered", 0) or 0) if isinstance(window_30, dict) else 0
        actions[1]["rationale"] = (
            f"Company growth computed across deterministic windows (7d runs={runs_7}, 30d runs={runs_30})."
        )

    return actions[:5]


def _build_insights_payload(
    insights_input: Dict[str, Any],
    *,
    provider: str,
    profile: str,
    run_id: str,
    candidate_id: str,
    status: str,
    reason: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    top_families = insights_input.get("top_families") if isinstance(insights_input.get("top_families"), list) else []
    top_skills = insights_input.get("top_skills") if isinstance(insights_input.get("top_skills"), list) else []
    top_titles = insights_input.get("top_titles") if isinstance(insights_input.get("top_titles"), list) else []

    themes: List[str] = []
    if top_titles:
        themes.append("Title concentration shifted in top-ranked roles.")
    if top_families:
        themes.append("Role family distribution remains concentrated.")
    if top_skills:
        themes.append("Structured skill-token mix indicates recurring capability demand.")
    while len(themes) < 3:
        themes.append("Trend windows are stable and deterministic for planning.")

    risks: List[str] = []
    penalties = (
        insights_input.get("most_common_penalties")
        if isinstance(insights_input.get("most_common_penalties"), list)
        else []
    )
    if penalties:
        risks.append("Recurring penalties may reduce fit if profile positioning is unchanged.")
    window_14 = _window_payload(insights_input, 14)
    if isinstance(window_14, dict) and int(window_14.get("runs_considered", 0) or 0) == 0:
        risks.append("Limited run history for 14-day trend window.")
    if not risks:
        risks.append("No elevated structured risk detected in current windows.")

    return {
        "schema_version": "ai_insights_output.v1",
        "status": status,
        "reason": reason,
        "provider": provider,
        "profile": profile,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "themes": themes[:5],
        "actions": _build_top_actions(insights_input, status=status),
        "top_roles": insights_input.get("top_roles") or [],
        "risks": risks[:3],
        "structured_inputs": {
            "job_counts": insights_input.get("job_counts") or {},
            "top_companies": insights_input.get("top_companies") or [],
            "top_titles": top_titles,
            "top_locations": insights_input.get("top_locations") or [],
            "top_skills": top_skills,
            "scoring_summary": insights_input.get("scoring_summary") or {},
            "trend_analysis": (insights_input.get("trend_analysis") or {}).get("windows")
            if isinstance(insights_input.get("trend_analysis"), dict)
            else [],
            "most_common_penalties": penalties,
            "strongest_positive_signals": insights_input.get("strongest_positive_signals") or [],
            "strongest_negative_signals": insights_input.get("strongest_negative_signals") or [],
            "score_distribution": insights_input.get("score_distribution") or {},
            "top_families": top_families,
            "diffs": insights_input.get("diffs") or {},
        },
        "metadata": metadata,
    }


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# Weekly AI Insights",
        "",
        f"Provider: **{payload.get('provider')}**",
        f"Profile: **{payload.get('profile')}**",
        f"Status: **{payload.get('status')}**",
        "",
    ]
    if payload.get("reason"):
        lines.append(f"Reason: {payload.get('reason')}")
        lines.append("")

    lines.append("## Themes")
    for theme in payload.get("themes") or []:
        lines.append(f"- {theme}")
    if not (payload.get("themes") or []):
        lines.append("- (none)")
    lines.append("")

    lines.append("## Top 5 Actions")
    actions = payload.get("actions") or []
    if actions:
        for action in actions:
            title = str(action.get("title") or "Action")
            rationale = str(action.get("rationale") or "")
            fields = ", ".join(action.get("supporting_evidence_fields") or [])
            lines.append(f"- **{title}**: {rationale}")
            lines.append(f"  - Evidence: {fields}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Top roles")
    for role in payload.get("top_roles") or []:
        title = role.get("title") or "Untitled"
        score = role.get("score", 0)
        url = role.get("apply_url") or ""
        if url:
            lines.append(f"- **{score}** {title} - {url}")
        else:
            lines.append(f"- **{score}** {title}")
    if not (payload.get("top_roles") or []):
        lines.append("- (none)")
    lines.append("")

    lines.append("## Risks")
    for risk in payload.get("risks") or []:
        lines.append(f"- {risk}")
    if not (payload.get("risks") or []):
        lines.append("- (none)")
    lines.append("")

    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    lines.append("## Metadata")
    for key in sorted(meta.keys()):
        lines.append(f"- {key}: {meta[key]}")
    lines.append("")
    return "\n".join(lines)


def _should_use_cache(existing: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    if not isinstance(existing, dict):
        return False
    existing_meta = existing.get("metadata")
    if not isinstance(existing_meta, dict):
        return False
    for key in ("cache_key", "structured_input_hash", "prompt_sha256", "prompt_version", "model", "provider"):
        if existing_meta.get(key) != metadata.get(key):
            return False
    return True


def _validate_output_payload(payload: Dict[str, Any]) -> List[str]:
    errors = validate_payload(payload, _output_schema())

    actions = payload.get("actions")
    if not isinstance(actions, list):
        errors.append("actions: expected array")
        return errors
    if len(actions) != 5:
        errors.append("actions: expected exactly 5 entries")

    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            errors.append(f"actions[{idx}]: expected object")
            continue
        fields = action.get("supporting_evidence_fields")
        if not isinstance(fields, list) or not fields:
            errors.append(f"actions[{idx}].supporting_evidence_fields: expected non-empty array")
            continue
        for field in fields:
            if not isinstance(field, str):
                errors.append(f"actions[{idx}].supporting_evidence_fields: non-string field")
                continue
            if field not in _ALLOWED_EVIDENCE_FIELDS:
                errors.append(f"actions[{idx}].supporting_evidence_fields: unsupported field `{field}`")

    return errors


def _write_error_artifact(run_dir: Path, profile: str, payload: Dict[str, Any]) -> Path:
    error_path = run_dir / f"ai_insights.{profile}.error.json"
    error_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return error_path


def _fail_closed_payload(
    *,
    insights_input: Dict[str, Any],
    provider: str,
    profile: str,
    run_id: str,
    candidate_id: str,
    metadata: Dict[str, Any],
    schema_errors: List[str],
    error_path: Path,
) -> Dict[str, Any]:
    payload = _build_insights_payload(
        insights_input,
        provider=provider,
        profile=profile,
        run_id=run_id,
        candidate_id=candidate_id,
        status="error",
        reason="output_schema_validation_failed",
        metadata={
            **metadata,
            "schema_errors": schema_errors,
            "error_artifact": str(error_path),
        },
    )
    payload_errors = _validate_output_payload(payload)
    if payload_errors:
        logger.error("Fail-closed insights payload still invalid: %s", "; ".join(payload_errors))
    return payload


def generate_insights(
    *,
    provider: str,
    profile: str,
    ranked_path: Path,
    prev_path: Optional[Path],
    run_id: str,
    prompt_path: Path = PROMPT_PATH,
    ai_enabled: bool,
    ai_reason: str,
    model_name: str,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
) -> Tuple[Path, Path, Dict[str, Any]]:
    prompt_text, prompt_sha = _load_prompt(prompt_path)
    _ = prompt_text.strip()
    ranked_families_path = ranked_path.parent / ranked_path.name.replace("ranked_jobs", "ranked_families")
    insights_input_path, insights_input_payload = build_weekly_insights_input(
        provider=provider,
        profile=profile,
        ranked_path=ranked_path,
        prev_path=prev_path,
        ranked_families_path=ranked_families_path if ranked_families_path.exists() else None,
        run_id=run_id,
        run_repository=_run_repository(),
        candidate_id=candidate_id,
        run_metadata_dir=RUN_METADATA_DIR,
    )

    structured_input_hash = _sha256_bytes(insights_input_path.read_bytes())
    input_hashes = {
        "insights_input": _sha256_bytes(insights_input_path.read_bytes()),
        "ranked": (insights_input_payload.get("input_hashes") or {}).get("ranked"),
        "previous": (insights_input_payload.get("input_hashes") or {}).get("previous"),
        "ranked_families": (insights_input_payload.get("input_hashes") or {}).get("ranked_families"),
    }
    cache_key = _sha256_bytes(
        json.dumps(
            {
                "prompt_version": PROMPT_VERSION,
                "prompt_sha256": prompt_sha,
                "model": model_name,
                "provider": provider,
                "profile": profile,
                "input_hashes": input_hashes,
                "structured_input_hash": structured_input_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )
    metadata = {
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha,
        "model": model_name,
        "provider": provider,
        "profile": profile,
        "timestamp": utc_now_iso(),
        "input_hashes": input_hashes,
        "structured_input_hash": structured_input_hash,
        "cache_key": cache_key,
    }
    rates = resolve_model_rates(model_name)

    run_dir = _run_dir(run_id, candidate_id=candidate_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / f"ai_insights.{profile}.json"
    md_path = run_dir / f"ai_insights.{profile}.md"

    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            existing = None
        if _should_use_cache(existing, metadata):
            logger.info("AI insights cache hit (%s/%s).", provider, profile)
            return md_path, json_path, existing

    if not ai_enabled:
        ai_accounting = {
            "model": model_name,
            "tokens_in": 0,
            "tokens_out": 0,
            "tokens_total": 0,
            "input_per_1k_usd": rates["input_per_1k"],
            "output_per_1k_usd": rates["output_per_1k"],
            "estimated_cost_usd": "0.000000",
        }
        payload = _build_insights_payload(
            insights_input_payload,
            provider=provider,
            profile=profile,
            run_id=run_id,
            candidate_id=candidate_id,
            status="disabled",
            reason=ai_reason,
            metadata={**metadata, "ai_accounting": ai_accounting},
        )
    else:
        payload = _build_insights_payload(
            insights_input_payload,
            provider=provider,
            profile=profile,
            run_id=run_id,
            candidate_id=candidate_id,
            status="ok",
            reason="",
            metadata=metadata,
        )
        tokens_in = estimate_tokens(
            json.dumps(insights_input_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        )
        tokens_out = estimate_tokens(
            json.dumps(
                {
                    "themes": payload.get("themes") or [],
                    "actions": payload.get("actions") or [],
                    "top_roles": payload.get("top_roles") or [],
                    "risks": payload.get("risks") or [],
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )
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
        payload["metadata"] = {**metadata, "ai_accounting": ai_accounting}

    schema_errors = _validate_output_payload(payload)
    if schema_errors:
        error_path = _write_error_artifact(
            run_dir,
            profile,
            {
                "error": "ai_insights_output_validation_failed",
                "schema_version": "ai_insights_output.v1",
                "run_id": run_id,
                "candidate_id": candidate_id,
                "provider": provider,
                "profile": profile,
                "schema_errors": schema_errors,
                "metadata": metadata,
                "generated_at": utc_now_iso(),
            },
        )
        payload = _fail_closed_payload(
            insights_input=insights_input_payload,
            provider=provider,
            profile=profile,
            run_id=run_id,
            candidate_id=candidate_id,
            metadata=metadata,
            schema_errors=schema_errors,
            error_path=error_path,
        )

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return md_path, json_path, payload
