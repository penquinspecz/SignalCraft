from __future__ import annotations

from pathlib import Path

import pytest

from ji_engine.providers.jsonld_provider import JsonLdProvider


def test_jsonld_provider_parses_snapshot_deterministically(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "xai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "index.html"
    snapshot_path.write_text(
        Path("tests/fixtures/providers/xai/index.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    provider = JsonLdProvider(
        provider_id="xai",
        careers_url="https://x.ai/careers",
        snapshot_dir=snapshot_dir,
        mode="SNAPSHOT",
    )
    first = [item.to_dict() for item in provider.load_from_snapshot()]
    second = [item.to_dict() for item in provider.load_from_snapshot()]

    assert first == second
    assert len(first) == 2
    assert [item["apply_url"] for item in first] == [
        "https://x.ai/careers/ml-inference-engineer",
        "https://x.ai/careers/sre-platform",
    ]


def test_jsonld_provider_rejects_invalid_snapshot(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "xai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "index.html").write_text("<html>tiny</html>", encoding="utf-8")

    provider = JsonLdProvider(
        provider_id="xai",
        careers_url="https://x.ai/careers",
        snapshot_dir=snapshot_dir,
        mode="SNAPSHOT",
    )
    with pytest.raises(RuntimeError, match="Invalid snapshot"):
        provider.load_from_snapshot()


def test_jsonld_provider_job_ids_are_stable(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "mistral_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "index.html"
    snapshot_path.write_text(
        Path("tests/fixtures/providers/mistral/index.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    provider = JsonLdProvider(
        provider_id="mistral",
        careers_url="https://mistral.ai/careers",
        snapshot_dir=snapshot_dir,
        mode="SNAPSHOT",
    )
    first = provider.load_from_snapshot()
    second = provider.load_from_snapshot()

    assert [item.job_id for item in first] == [item.job_id for item in second]
    assert all(item.job_id for item in first)


def test_jsonld_provider_huggingface_required_fields_and_order(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "huggingface_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "index.html"
    snapshot_path.write_text(
        Path("tests/fixtures/providers/huggingface/index.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    provider = JsonLdProvider(
        provider_id="huggingface",
        careers_url="https://huggingface.co/jobs",
        snapshot_dir=snapshot_dir,
        mode="SNAPSHOT",
    )
    first = [item.to_dict() for item in provider.load_from_snapshot()]
    second = [item.to_dict() for item in provider.load_from_snapshot()]
    jobs = first

    assert [job["apply_url"] for job in jobs] == [
        "https://huggingface.co/jobs/research-engineer-llm-evaluation",
        "https://huggingface.co/jobs/staff-software-engineer-platform",
    ]
    assert [job["job_id"] for job in first] == [job["job_id"] for job in second]
    for job in jobs:
        assert job["title"]
        assert job["apply_url"]
        assert job["detail_url"] == job["apply_url"]
        assert job["job_id"]
