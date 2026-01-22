from pathlib import Path

from jobintel.enrichment import enrich_jobs


def test_enrichment_rules() -> None:
    job = {
        "title": "Senior Security Engineer L4",
        "location": "Remote - US",
        "department": "Security",
        "description": "Build solutions for government customers.",
    }
    enriched = enrich_jobs([job], cache_dir=None)[0]["enrichment"]

    assert enriched["inferred_seniority"] == "Senior IC"
    assert enriched["inferred_remote"] == "remote"
    assert enriched["inferred_level"] == "L4"
    assert enriched["normalized_location"] == "remote"
    assert enriched["inferred_domain_tags"] == ["gov", "security"]


def test_enrichment_cache_behavior(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    job = {
        "id": "job-1",
        "title": "Support Engineer",
        "location": "Onsite",
        "description": "Customer success role.",
    }
    first = enrich_jobs([job], cache_dir=cache_dir)[0]["enrichment"]
    second = enrich_jobs([job], cache_dir=cache_dir)[0]["enrichment"]

    assert first == second

    updated = {**job, "description": "Customer success role. Remote."}
    third = enrich_jobs([updated], cache_dir=cache_dir)[0]["enrichment"]
    assert third["inferred_remote"] == "remote"
    assert third != first
