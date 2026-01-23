from pathlib import Path

from ji_engine.providers.ashby_provider import AshbyProvider
from ji_engine.providers.registry import load_providers_config
from ji_engine.utils.job_id import extract_job_id_from_url


def test_openai_snapshot_contract() -> None:
    snapshot_path = Path("data/openai_snapshots/index.html")
    assert snapshot_path.exists(), f"Missing snapshot fixture: {snapshot_path}"
    provider = AshbyProvider(
        provider_id="openai",
        board_url="https://jobs.ashbyhq.com/openai",
        snapshot_dir=Path("data/openai_snapshots"),
        mode="SNAPSHOT",
    )
    jobs = provider.load_from_snapshot()
    assert len(jobs) > 100

    apply_urls = [job.apply_url for job in jobs if job.apply_url]
    assert len(apply_urls) / len(jobs) >= 0.8

    job_ids = [extract_job_id_from_url(url) for url in apply_urls]
    with_job_id = sum(1 for jid in job_ids if jid)
    assert with_job_id / len(jobs) >= 0.8


def test_ashby_snapshots_exist() -> None:
    providers = load_providers_config(Path("config/providers.json"))
    ashby_entries = [p for p in providers if p.get("type") == "ashby"]
    assert ashby_entries
    missing: list[str] = []
    for entry in ashby_entries:
        snapshot_path = Path(entry["snapshot_path"])
        if not snapshot_path.exists():
            missing.append(str(snapshot_path))
            continue
        assert snapshot_path.stat().st_size > 0
    assert not missing, f"Missing ashby snapshot fixtures: {', '.join(sorted(missing))}"
