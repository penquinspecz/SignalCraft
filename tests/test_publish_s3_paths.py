from scripts.publish_s3 import build_s3_prefixes


def test_build_s3_prefixes() -> None:
    prefixes = build_s3_prefixes("jobintel", "2026-01-22T00:00:00Z", {"openai": {"cs": "jobintel/latest/openai/cs"}})
    assert prefixes["runs"] == "jobintel/runs/2026-01-22T00:00:00Z"
    assert prefixes["latest"]["openai"]["cs"] == "jobintel/latest/openai/cs"


def test_build_s3_prefixes_namespaced_candidate() -> None:
    prefixes = build_s3_prefixes(
        "jobintel",
        "2026-01-22T00:00:00Z",
        {"openai": {"cs": "jobintel/candidates/alice/latest/openai/cs"}},
        candidate_id="alice",
    )
    assert prefixes["runs"] == "jobintel/candidates/alice/runs/2026-01-22T00:00:00Z"
    assert prefixes["latest"]["openai"]["cs"] == "jobintel/candidates/alice/latest/openai/cs"
