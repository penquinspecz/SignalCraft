from __future__ import annotations

from ji_engine.roadmap_discipline import RoadmapStamp, evaluate_roadmap_guard, parse_last_verified_stamp


def test_parse_last_verified_stamp_ok() -> None:
    text = "x\nLast verified: `2026-02-07T03:41:49Z` @ `0d3b694`\ny\n"
    stamp = parse_last_verified_stamp(text)
    assert stamp is not None
    assert stamp.timestamp_utc == "2026-02-07T03:41:49Z"
    assert stamp.sha == "0d3b694"


def test_parse_last_verified_stamp_missing() -> None:
    assert parse_last_verified_stamp("no stamp here") is None


def test_guard_requires_roadmap_when_receipts_change() -> None:
    result = evaluate_roadmap_guard(
        stamp=RoadmapStamp(timestamp_utc="2026-02-07T03:41:49Z", sha="0d3b694"),
        changed_files=[
            "ops/proof/bundles/m3-abc/infra/receipt.json",
            "scripts/check_roadmap_discipline.py",
        ],
        head_sha="0d3b694",
    )
    codes = {f.code for f in result.findings}
    assert "roadmap_required_for_receipt_changes" in codes
    assert result.has_errors is True


def test_guard_warns_for_core_without_roadmap() -> None:
    result = evaluate_roadmap_guard(
        stamp=RoadmapStamp(timestamp_utc="2026-02-07T03:41:49Z", sha="0d3b694"),
        changed_files=["scripts/run_daily.py"],
        head_sha="0d3b694",
    )
    codes = {f.code for f in result.findings}
    assert "roadmap_missing_for_core_changes" in codes
    assert result.has_warnings is True
    assert result.has_errors is False


def test_guard_stale_detection_from_files_since_stamp() -> None:
    result = evaluate_roadmap_guard(
        stamp=RoadmapStamp(timestamp_utc="2026-02-07T03:41:49Z", sha="aaaaaaa"),
        changed_files=["scripts/run_daily.py"],
        head_sha="bbbbbbb",
        files_since_stamp=["scripts/run_daily.py", "tests/test_roadmap_discipline.py"],
        commits_since_stamp=100,
        stale_commit_threshold=50,
    )
    codes = {f.code for f in result.findings}
    assert "stamp_stale_vs_sensitive_changes" in codes
    assert "stamp_wildly_stale" in codes


def test_guard_passes_when_roadmap_is_updated_with_sensitive_changes() -> None:
    result = evaluate_roadmap_guard(
        stamp=RoadmapStamp(timestamp_utc="2026-02-07T03:41:49Z", sha="0d3b694"),
        changed_files=[
            "docs/ROADMAP.md",
            "ops/proof/bundles/m3-abc/infra/receipt.json",
            "scripts/run_daily.py",
        ],
        head_sha="0d3b694",
    )
    assert result.findings == ()
