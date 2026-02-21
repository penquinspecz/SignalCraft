from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest

import ji_engine.artifacts.catalog as artifact_catalog
from ji_engine.artifacts.catalog import ArtifactCategory, get_artifact_category
from ji_engine.pipeline import artifact_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"

# Canonical UI-safe artifacts for contract validation.
_CANONICAL_UI_SAFE_ARTIFACTS: Dict[str, str] = {
    "run_summary.v1.json": "run_summary.schema.v1.json",
    "provider_availability_v1.json": "provider_availability.schema.v1.json",
    "explanation_v1.json": "explanation.schema.v1.json",
    "ai_insights.cs.json": "ai_insights_output.schema.v1.json",
    "ai_job_briefs.cs.json": "ai_job_brief.schema.v1.json",
}

# Dashboard schema-version exposure is only applicable to v1 run/indexed JSON contracts.
_DASHBOARD_SCHEMA_VERSION_KEYS = {
    "run_summary.v1.json": 1,
    "provider_availability_v1.json": 1,
    "explanation_v1.json": 1,
}


def _ui_safe_catalog_exact_keys() -> List[str]:
    keys = [
        key
        for key, category in artifact_catalog._ARTIFACT_CATALOG.items()  # noqa: SLF001
        if category == ArtifactCategory.UI_SAFE
    ]
    return sorted(keys)


def _ui_safe_catalog_patterns() -> List[str]:
    patterns = [
        pattern
        for pattern, category in artifact_catalog._ARTIFACT_PATTERNS  # noqa: SLF001
        if category == ArtifactCategory.UI_SAFE
    ]
    return sorted(patterns)


def test_ui_safe_catalog_artifacts_have_schema_files() -> None:
    exact_keys = _ui_safe_catalog_exact_keys()
    patterns = _ui_safe_catalog_patterns()

    # Stable contract set: exact UI-safe keys plus profile-keyed pattern representatives.
    assert exact_keys == [
        "explanation_v1.json",
        "provider_availability_v1.json",
        "run_summary.v1.json",
    ]
    assert patterns == ["*ai_insights*.json", "*ai_job_briefs*.json"]

    for artifact_key, schema_filename in sorted(_CANONICAL_UI_SAFE_ARTIFACTS.items()):
        assert get_artifact_category(artifact_key) == ArtifactCategory.UI_SAFE
        schema_path = SCHEMA_DIR / schema_filename
        assert schema_path.exists(), f"Missing schema for {artifact_key}: {schema_filename}"


def test_dashboard_schema_versions_exposed_for_applicable_ui_safe_artifacts() -> None:
    pytest.importorskip("fastapi")
    import ji_engine.dashboard.app as dashboard_app

    for artifact_key, expected_version in sorted(_DASHBOARD_SCHEMA_VERSION_KEYS.items()):
        actual = dashboard_app._schema_version_for_artifact_key(artifact_key)  # noqa: SLF001
        assert actual == expected_version, f"Dashboard schema version mismatch for {artifact_key}"


def test_run_artifact_path_helpers_cover_canonical_ui_safe_run_artifacts() -> None:
    run_dir = Path("state/candidates/local/runs/20260221T000000Z")

    helper_paths = {
        "run_summary.v1.json": artifact_paths.run_summary_path(run_dir).as_posix(),
        "provider_availability_v1.json": artifact_paths.provider_availability_path(run_dir).as_posix(),
        "explanation_v1.json": artifact_paths.explanation_path(run_dir).as_posix(),
        "ai_insights.cs.json": artifact_paths.ai_insights_path(run_dir, "cs").as_posix(),
        "ai_job_briefs.cs.json": artifact_paths.ai_job_briefs_path(run_dir, "cs").as_posix(),
    }

    assert helper_paths["run_summary.v1.json"].endswith("/run_summary.v1.json")
    assert helper_paths["provider_availability_v1.json"].endswith("/artifacts/provider_availability_v1.json")
    assert helper_paths["explanation_v1.json"].endswith("/artifacts/explanation_v1.json")
    assert helper_paths["ai_insights.cs.json"].endswith("/artifacts/ai_insights.cs.json")
    assert helper_paths["ai_job_briefs.cs.json"].endswith("/artifacts/ai_job_briefs.cs.json")


def test_no_orphan_artifact_schemas_in_guarded_contract_set() -> None:
    catalog_registered = set(_ui_safe_catalog_exact_keys())
    catalog_registered.update({"ai_insights.cs.json", "ai_job_briefs.cs.json"})

    schema_by_artifact = {
        key: value
        for key, value in sorted(_CANONICAL_UI_SAFE_ARTIFACTS.items())
        if key in catalog_registered
    }

    missing_registrations = [
        key for key in sorted(schema_by_artifact) if get_artifact_category(key) == ArtifactCategory.UNCATEGORIZED
    ]
    assert not missing_registrations, f"Orphan artifact schemas detected: {missing_registrations}"
