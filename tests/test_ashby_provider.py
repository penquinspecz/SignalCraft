from pathlib import Path

from ji_engine.providers.ashby_provider import AshbyProvider


def test_ashby_provider_parses_fixture() -> None:
    snapshot_dir = Path("tests/fixtures/ashby")
    provider = AshbyProvider(
        provider_id="anthropic",
        board_url="https://jobs.ashbyhq.com/anthropic",
        snapshot_dir=snapshot_dir,
        mode="SNAPSHOT",
    )
    jobs = provider.load_from_snapshot()
    assert len(jobs) == 2
    assert all(job.apply_url for job in jobs)
    assert all(job.job_id for job in jobs)
    assert jobs[0].job_id != jobs[1].job_id


def test_openai_snapshot_smallish_allowed(tmp_path: Path, monkeypatch) -> None:
    snapshot_dir = tmp_path / "openai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "index.html"
    snapshot_path.write_text("<html>ok</html>" + (" " * 7000), encoding="utf-8")
    provider = AshbyProvider(
        provider_id="openai",
        board_url="https://jobs.ashbyhq.com/openai",
        snapshot_dir=snapshot_dir,
        mode="SNAPSHOT",
    )
    monkeypatch.setattr(provider, "_parse_html", lambda _html: [])
    provider.load_from_snapshot()


def test_openai_snapshot_cloudflare_rejected(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "openai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "index.html"
    payload = "<html><title>Just a moment...</title>cf_chl_opt</html>" + (" " * 2000)
    snapshot_path.write_text(payload, encoding="utf-8")
    provider = AshbyProvider(
        provider_id="openai",
        board_url="https://jobs.ashbyhq.com/openai",
        snapshot_dir=snapshot_dir,
        mode="SNAPSHOT",
    )
    try:
        provider.load_from_snapshot()
    except RuntimeError as exc:
        assert "cloudflare" in str(exc).lower()
    else:
        raise AssertionError("Expected cloudflare snapshot to be rejected")


def test_new_ashby_providers_parse_stably_from_fixtures(tmp_path: Path) -> None:
    cases = [
        ("scaleai", "https://jobs.ashbyhq.com/scaleai", Path("tests/fixtures/providers/scaleai/index.html")),
        ("replit", "https://jobs.ashbyhq.com/replit", Path("tests/fixtures/providers/replit/index.html")),
    ]
    for provider_id, board_url, fixture in cases:
        snapshot_dir = tmp_path / f"{provider_id}_snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "index.html").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

        provider = AshbyProvider(
            provider_id=provider_id,
            board_url=board_url,
            snapshot_dir=snapshot_dir,
            mode="SNAPSHOT",
        )
        first = [item.to_dict() for item in provider.load_from_snapshot()]
        second = [item.to_dict() for item in provider.load_from_snapshot()]

        assert len(first) == 2
        assert [job["apply_url"] for job in first] == [job["apply_url"] for job in second]
        assert [job["job_id"] for job in first] == [job["job_id"] for job in second]
        assert [job["apply_url"] for job in first] == sorted(job["apply_url"] for job in first)
        for job in first:
            assert job["job_id"]
            assert job["title"]
            assert job["apply_url"]
