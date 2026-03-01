"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import fnmatch
import json
from typing import Any, Dict, List, Tuple

# Prohibited fields in UI-safe artifacts (raw JD, secrets)
_UI_SAFE_PROHIBITED_KEYS = frozenset(
    {
        "jd_text",
        "description",
        "description_text",
        "descriptionHtml",
        "job_description",
    }
)

# Exact artifact key -> category
_ARTIFACT_CATALOG: Dict[str, str] = {
    "run_summary.v1.json": "ui_safe",
    "run_health.v1.json": "replay_safe",
    "run_report.json": "replay_safe",
    "provider_availability_v1.json": "ui_safe",
    "explanation_v1.json": "ui_safe",
    "digest_v1.json": "ui_safe",
    "job_timeline_v1.json": "ui_safe",
    "digest_receipt_v1.json": "replay_safe",
}

# Pattern -> category (checked in order; first match wins)
_ARTIFACT_PATTERNS: List[Tuple[str, str]] = [
    ("*ranked_jobs*.json", "replay_safe"),
    ("*ranked_jobs*.csv", "replay_safe"),
    ("*ranked_families*.json", "replay_safe"),
    ("*shortlist*.md", "replay_safe"),
    ("*_top_*.md", "replay_safe"),
    ("*alerts*.json", "replay_safe"),
    ("*alerts*.md", "replay_safe"),
    ("*raw_jobs*.json", "replay_safe"),
    ("*labeled_jobs*.json", "replay_safe"),
    ("*enriched_jobs*.json", "replay_safe"),
    ("*ai_insights*.json", "ui_safe"),
    ("*ai_job_briefs*.json", "ui_safe"),
]

# Canonical representatives for pattern-based UI-safe artifact families.
UI_SAFE_PATTERN_REPRESENTATIVE_KEYS: Dict[str, str] = {
    "*ai_insights*.json": "ai_insights.cs.json",
    "*ai_job_briefs*.json": "ai_job_briefs.cs.json",
}

# Canonical UI-safe artifacts that are schema-backed.
UI_SAFE_SCHEMA_SPECS: Dict[str, Tuple[str, int]] = {
    "run_summary.v1.json": ("run_summary", 1),
    "provider_availability_v1.json": ("provider_availability", 1),
    "explanation_v1.json": ("explanation", 1),
    "digest_v1.json": ("digest", 1),
    "job_timeline_v1.json": ("job_timeline", 1),
    "ai_insights.cs.json": ("ai_insights_output", 1),
    "ai_job_briefs.cs.json": ("ai_job_brief", 1),
}

# Canonical UI-safe artifacts without dedicated JSON Schema files.
UI_SAFE_NONSCHEMA_CANONICAL_KEYS: Tuple[str, ...] = ("ai_job_briefs.cs.error.json",)

# Dashboard schema-version exposure for indexed run artifacts.
DASHBOARD_SCHEMA_VERSION_BY_ARTIFACT_KEY: Dict[str, int] = {
    "run_summary.v1.json": 1,
    "run_health.v1.json": 1,
    "provider_availability_v1.json": 1,
    "explanation_v1.json": 1,
    "digest_v1.json": 1,
    "job_timeline_v1.json": 1,
    "run_report.json": 1,
}

# Artifact keys whose payloads are schema-validated at serving/write boundaries.
_SCHEMA_SPECS_BY_EXACT_ARTIFACT_KEY: Dict[str, Tuple[str, int]] = {
    "run_report.json": ("run_report", 1),
    "run_health.v1.json": ("run_health", 1),
    "run_summary.v1.json": ("run_summary", 1),
    "provider_availability_v1.json": ("provider_availability", 1),
    "explanation_v1.json": ("explanation", 1),
    "digest_v1.json": ("digest", 1),
    "job_timeline_v1.json": ("job_timeline", 1),
}


class ArtifactCategory:
    """Artifact model v2 categories."""

    UI_SAFE = "ui_safe"
    REPLAY_SAFE = "replay_safe"
    UNCATEGORIZED = "uncategorized"


def get_artifact_category(artifact_key: str) -> str:
    """
    Look up artifact key in catalog. Returns ui_safe, replay_safe, or uncategorized.
    """
    if not isinstance(artifact_key, str) or not artifact_key.strip():
        return ArtifactCategory.UNCATEGORIZED
    key = artifact_key.strip()
    if key in _ARTIFACT_CATALOG:
        return _ARTIFACT_CATALOG[key]
    for pattern, category in _ARTIFACT_PATTERNS:
        if fnmatch.fnmatch(key, pattern):
            return category
    return ArtifactCategory.UNCATEGORIZED


# Exported for tests and dashboard
FORBIDDEN_JD_KEYS = frozenset(_UI_SAFE_PROHIBITED_KEYS)


def ui_safe_catalog_exact_keys() -> List[str]:
    """Return deterministic, sorted UI-safe exact keys from the artifact catalog."""
    keys = [key for key, category in _ARTIFACT_CATALOG.items() if category == ArtifactCategory.UI_SAFE]
    return sorted(keys)


def ui_safe_catalog_patterns() -> List[str]:
    """Return deterministic, sorted UI-safe patterns from the artifact catalog."""
    patterns = [pattern for pattern, category in _ARTIFACT_PATTERNS if category == ArtifactCategory.UI_SAFE]
    return sorted(patterns)


def canonical_ui_safe_artifact_keys() -> List[str]:
    """
    Return deterministic canonical UI-safe artifact keys for contract checks.
    Includes exact UI-safe keys, pattern representatives, and non-schema contract artifacts.
    """
    keys = set(ui_safe_catalog_exact_keys())
    keys.update(UI_SAFE_PATTERN_REPRESENTATIVE_KEYS.values())
    keys.update(UI_SAFE_NONSCHEMA_CANONICAL_KEYS)
    return sorted(keys)


def assert_no_forbidden_fields(obj: object, context: str = "") -> None:
    """
    Fail-closed: raise ValueError if obj contains any forbidden JD keys.
    Use for UI-safe endpoints. Redaction is only for replay-safe/legacy paths.
    """
    violations = _scan_prohibited(obj)
    if violations:
        msg = json.dumps(
            {"error": "forbidden_jd_fields", "context": context, "violations": violations},
            sort_keys=True,
        )
        raise ValueError(msg)


def redact_forbidden_fields(obj: object) -> object:
    """
    Recursively remove forbidden JD-related keys from a JSON-serializable structure.
    Returns a copy; does not mutate input. Used to ensure API responses never leak raw JD.
    """
    if isinstance(obj, dict):
        return {
            k: redact_forbidden_fields(v)
            for k, v in obj.items()
            if k not in _UI_SAFE_PROHIBITED_KEYS
            and (k.lower() if isinstance(k, str) else "") not in {x.lower() for x in _UI_SAFE_PROHIBITED_KEYS}
        }
    if isinstance(obj, list):
        return [redact_forbidden_fields(item) for item in obj]
    return obj


def _scan_prohibited(value: object, path: str = "") -> List[str]:
    """Recursively find prohibited keys in a JSON-serializable value."""
    violations: List[str] = []
    if isinstance(value, dict):
        for k in value:
            k_lower = k.lower() if isinstance(k, str) else ""
            if k in _UI_SAFE_PROHIBITED_KEYS or k_lower in {x.lower() for x in _UI_SAFE_PROHIBITED_KEYS}:
                violations.append(f"{path}.{k}" if path else k)
            child = f"{path}.{k}" if path else str(k)
            violations.extend(_scan_prohibited(value[k], child))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            violations.extend(_scan_prohibited(item, f"{path}[{i}]"))
    return violations


def _assert_ui_safe_no_prohibited(payload: Dict[str, Any], artifact_key: str, run_id: str) -> None:
    """Raise ValueError if payload contains prohibited UI-safe fields."""
    violations = _scan_prohibited(payload)
    if violations:
        raise ValueError(
            json.dumps(
                {
                    "error": "ui_safe_prohibition_violation",
                    "artifact_key": artifact_key,
                    "run_id": run_id,
                    "violations": violations,
                },
                sort_keys=True,
            )
        )


def _load_schema_cached(schema_name: str, version: int) -> Dict[str, Any]:
    """Load schema once; module-level cache."""
    cache_key = f"{schema_name}.v{version}"
    if not hasattr(_load_schema_cached, "_cache"):
        _load_schema_cached._cache = {}
    if cache_key not in _load_schema_cached._cache:
        try:
            from scripts.schema_validate import resolve_named_schema_path
        except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
            from schema_validate import resolve_named_schema_path  # type: ignore

        path = resolve_named_schema_path(schema_name, version)
        _load_schema_cached._cache[cache_key] = json.loads(path.read_text(encoding="utf-8"))
    return _load_schema_cached._cache[cache_key]


def schema_spec_for_artifact_key(artifact_key: str) -> Tuple[str, int] | None:
    """Return schema spec (name, version) for artifacts that are schema-validated by contract."""
    if artifact_key in _SCHEMA_SPECS_BY_EXACT_ARTIFACT_KEY:
        return _SCHEMA_SPECS_BY_EXACT_ARTIFACT_KEY[artifact_key]
    if "run_health" in artifact_key:
        return ("run_health", 1)
    if "run_summary" in artifact_key:
        return ("run_summary", 1)
    return None


def _validate_against_schema(payload: Dict[str, Any], artifact_key: str) -> List[str]:
    """Validate artifact against its native schema. Returns list of errors."""
    try:
        from scripts.schema_validate import validate_payload
    except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
        from schema_validate import validate_payload  # type: ignore

    schema_spec = schema_spec_for_artifact_key(artifact_key)
    if schema_spec is None:
        return []
    schema = _load_schema_cached(*schema_spec)
    return validate_payload(payload, schema)


def validate_artifact_payload(
    payload: Dict[str, Any],
    artifact_key: str,
    run_id: str,
    category: str,
) -> None:
    """
    Validate artifact payload against artifact model v2.
    Raises ValueError with structured message on failure.
    """
    if category == ArtifactCategory.UNCATEGORIZED:
        raise ValueError(
            json.dumps(
                {
                    "error": "artifact_uncategorized",
                    "artifact_key": artifact_key,
                    "run_id": run_id,
                    "message": "Artifact not in catalog; fail-closed.",
                },
                sort_keys=True,
            )
        )
    if category == ArtifactCategory.UI_SAFE:
        _assert_ui_safe_no_prohibited(payload, artifact_key, run_id)
        errors = _validate_against_schema(payload, artifact_key)
        if errors:
            raise ValueError(
                json.dumps(
                    {
                        "error": "ui_safe_validation_failed",
                        "artifact_key": artifact_key,
                        "run_id": run_id,
                        "schema_errors": errors,
                    },
                    sort_keys=True,
                )
            )
    elif category == ArtifactCategory.REPLAY_SAFE:
        errors = _validate_against_schema(payload, artifact_key)
        if errors:
            raise ValueError(
                json.dumps(
                    {
                        "error": "replay_safe_validation_failed",
                        "artifact_key": artifact_key,
                        "run_id": run_id,
                        "schema_errors": errors,
                    },
                    sort_keys=True,
                )
            )
