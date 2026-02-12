from __future__ import annotations

from ji_engine.semantic.cache import build_embedding_cache_key
from ji_engine.semantic.core import SEMANTIC_NORM_VERSION
from ji_engine.semantic.normalization import (
    normalize_job_text_semantic_norm_v1,
    semantic_content_hash_v1,
)


def test_semantic_job_normalization_stable_across_formatting_variants() -> None:
    variant_a = {
        "title": "  Senior, CUSTOMER-SUCCESS Engineer!!! ",
        "location": "Remote - US",
        "team": "Enterprise  AI",
        "description": "Own onboarding;\nrenewals\tand adoption outcomes.",
    }
    variant_b = {
        "title": "senior customer success engineer",
        "locationName": "remote us",
        "departmentName": "enterprise ai",
        "jd_text": "own onboarding renewals and adoption outcomes",
    }

    norm_a = normalize_job_text_semantic_norm_v1(variant_a)
    norm_b = normalize_job_text_semantic_norm_v1(variant_b)
    assert norm_a == norm_b
    assert semantic_content_hash_v1(norm_a) == semantic_content_hash_v1(norm_b)


def test_semantic_job_normalization_field_order_is_deterministic() -> None:
    lhs = {
        "description": "Drive renewals and expansion.",
        "team": "Customer Success",
        "location": "Remote US",
        "title": "Customer Success Manager",
    }
    rhs = {
        "title": "Customer Success Manager",
        "location": "Remote US",
        "team": "Customer Success",
        "description": "Drive renewals and expansion.",
    }
    assert normalize_job_text_semantic_norm_v1(lhs) == normalize_job_text_semantic_norm_v1(rhs)


def test_norm_version_change_alters_cache_key_inputs() -> None:
    normalized = normalize_job_text_semantic_norm_v1(
        {
            "title": "Solutions Architect",
            "location": "San Francisco",
            "team": "Deployment",
            "summary": "Build reliable AI rollouts",
        }
    )
    content_hash_v1 = semantic_content_hash_v1(normalized, norm_version=SEMANTIC_NORM_VERSION)
    key_v1 = build_embedding_cache_key(
        job_id="job-123",
        job_content_hash=content_hash_v1,
        candidate_profile_hash="profile-abc",
        norm_version=SEMANTIC_NORM_VERSION,
    )
    content_hash_v2 = semantic_content_hash_v1(normalized, norm_version="semantic_norm_v2")
    key_v2 = build_embedding_cache_key(
        job_id="job-123",
        job_content_hash=content_hash_v2,
        candidate_profile_hash="profile-abc",
        norm_version="semantic_norm_v2",
    )
    assert key_v1 != key_v2
