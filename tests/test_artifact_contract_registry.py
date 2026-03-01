from __future__ import annotations

from pathlib import Path

import pytest

import ji_engine.artifacts.catalog as artifact_catalog
from ji_engine.artifacts.catalog import ArtifactCategory, get_artifact_category, schema_spec_for_artifact_key
from ji_engine.pipeline import artifact_paths
from scripts import dashboard_offline_sanity
from scripts.schema_validate import resolve_named_schema_path


def test_ui_safe_catalog_contract_is_deterministic() -> None:
    exact_keys = artifact_catalog.ui_safe_catalog_exact_keys()
    patterns = artifact_catalog.ui_safe_catalog_patterns()
    canonical_keys = artifact_catalog.canonical_ui_safe_artifact_keys()
    expected_canonical = sorted(
        set(exact_keys)
        | set(artifact_catalog.UI_SAFE_PATTERN_REPRESENTATIVE_KEYS.values())
        | set(artifact_catalog.UI_SAFE_NONSCHEMA_CANONICAL_KEYS)
    )

    assert exact_keys == [
        "digest_v1.json",
        "explanation_v1.json",
        "provider_availability_v1.json",
        "run_summary.v1.json",
    ]
    assert patterns == sorted(artifact_catalog.UI_SAFE_PATTERN_REPRESENTATIVE_KEYS.keys())
    assert canonical_keys == expected_canonical


def test_ui_safe_schema_specs_have_schema_files_and_ui_categories() -> None:
    canonical_keys = set(artifact_catalog.canonical_ui_safe_artifact_keys())
    for artifact_key, schema_spec in sorted(artifact_catalog.UI_SAFE_SCHEMA_SPECS.items()):
        assert get_artifact_category(artifact_key) == ArtifactCategory.UI_SAFE
        assert artifact_key in canonical_keys
        schema_name, schema_version = schema_spec
        schema_path = resolve_named_schema_path(schema_name, schema_version)
        assert schema_path.exists(), f"Missing schema for {artifact_key}: {schema_name}.v{schema_version}"


def test_dashboard_schema_versions_align_with_validation_registry() -> None:
    pytest.importorskip("fastapi")
    import ji_engine.dashboard.app as dashboard_app

    for artifact_key, expected_version in sorted(artifact_catalog.DASHBOARD_SCHEMA_VERSION_BY_ARTIFACT_KEY.items()):
        actual = dashboard_app._schema_version_for_artifact_key(artifact_key)  # noqa: SLF001
        assert actual == expected_version, f"Dashboard schema version mismatch for {artifact_key}"
        assert schema_spec_for_artifact_key(artifact_key) is not None


def test_run_artifact_path_helpers_cover_canonical_ui_safe_run_artifacts() -> None:
    run_dir = Path("state/candidates/local/runs/20260221T000000Z")

    helper_paths = {
        "run_summary.v1.json": artifact_paths.run_summary_path(run_dir).as_posix(),
        "provider_availability_v1.json": artifact_paths.provider_availability_path(run_dir).as_posix(),
        "explanation_v1.json": artifact_paths.explanation_path(run_dir).as_posix(),
        "digest_v1.json": artifact_paths.digest_path(run_dir).as_posix(),
        "digest_receipt_v1.json": artifact_paths.digest_receipt_path(run_dir).as_posix(),
        "ai_insights.cs.json": artifact_paths.ai_insights_path(run_dir, "cs").as_posix(),
        "ai_job_briefs.cs.json": artifact_paths.ai_job_briefs_path(run_dir, "cs").as_posix(),
        "ai_job_briefs.cs.error.json": artifact_paths.ai_job_briefs_error_path(run_dir, "cs").as_posix(),
    }

    assert helper_paths["run_summary.v1.json"].endswith("/run_summary.v1.json")
    assert helper_paths["provider_availability_v1.json"].endswith("/artifacts/provider_availability_v1.json")
    assert helper_paths["explanation_v1.json"].endswith("/artifacts/explanation_v1.json")
    assert helper_paths["digest_v1.json"].endswith("/artifacts/digest_v1.json")
    assert helper_paths["digest_receipt_v1.json"].endswith("/artifacts/digest_receipt_v1.json")
    assert helper_paths["ai_insights.cs.json"].endswith("/artifacts/ai_insights.cs.json")
    assert helper_paths["ai_job_briefs.cs.json"].endswith("/artifacts/ai_job_briefs.cs.json")
    assert helper_paths["ai_job_briefs.cs.error.json"].endswith("/artifacts/ai_job_briefs.cs.error.json")


def test_dashboard_offline_sanity_cases_match_canonical_ui_safe_contract() -> None:
    cases = dashboard_offline_sanity.artifact_cases()
    assert sorted(cases.keys()) == artifact_catalog.canonical_ui_safe_artifact_keys()
    for artifact_key in sorted(cases):
        assert get_artifact_category(artifact_key) == ArtifactCategory.UI_SAFE


def test_no_orphan_schema_specs_or_pattern_representatives() -> None:
    patterns = set(artifact_catalog.ui_safe_catalog_patterns())
    representatives = set(artifact_catalog.UI_SAFE_PATTERN_REPRESENTATIVE_KEYS.keys())
    assert patterns == representatives

    canonical = set(artifact_catalog.canonical_ui_safe_artifact_keys())
    missing_schema_or_nonschema = [
        key
        for key in sorted(canonical)
        if key not in artifact_catalog.UI_SAFE_SCHEMA_SPECS
        and key not in artifact_catalog.UI_SAFE_NONSCHEMA_CANONICAL_KEYS
    ]
    assert not missing_schema_or_nonschema
