from __future__ import annotations

import importlib
import json
from pathlib import Path

import scripts.run_scrape as run_scrape_module


def _providers_payload(snapshot_path: Path, *, mode: str = "snapshot") -> dict:
    return {
        "schema_version": 1,
        "providers": [
            {
                "provider_id": "scaleai",
                "display_name": "Scale AI",
                "enabled": True,
                "careers_urls": ["https://jobs.ashbyhq.com/scaleai"],
                "allowed_domains": ["jobs.ashbyhq.com"],
                "extraction_mode": "ashby_api",
                "mode": mode,
                "snapshot_path": str(snapshot_path),
                "snapshot_dir": str(snapshot_path.parent),
                "live_enabled": True,
                "update_cadence": "daily",
            }
        ],
    }


def test_run_scrape_marks_unavailable_on_deny_with_reason_and_mode(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = data_dir / "scaleai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "index.html"
    snapshot_path.write_text(
        Path("tests/fixtures/providers/scaleai/index.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    providers_path = tmp_path / "providers.json"
    providers_path.write_text(json.dumps(_providers_payload(snapshot_path, mode="live")), encoding="utf-8")

    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    import ji_engine.config as config

    importlib.reload(config)
    run_scrape = importlib.reload(run_scrape_module)
    monkeypatch.setattr(
        run_scrape,
        "evaluate_robots_policy",
        lambda _url, provider_id=None: {
            "provider_id": provider_id,
            "host": "jobs.ashbyhq.com",
            "robots_url": "https://jobs.ashbyhq.com/robots.txt",
            "robots_fetched": True,
            "robots_status": 200,
            "robots_allowed": False,
            "allowlist_allowed": False,
            "final_allowed": False,
            "reason": "deny",
            "user_agent": "jobintel-bot/1.0",
            "allowlist_entries": [],
        },
    )

    rc = run_scrape.main(["--providers", "scaleai", "--mode", "LIVE", "--providers-config", str(providers_path)])
    assert rc == 0

    payload = json.loads((data_dir / "ashby_cache" / "scaleai_scrape_meta.json").read_text(encoding="utf-8"))
    assert payload["provider_id"] == "scaleai"
    assert payload["extraction_mode"] == "ashby"
    assert payload["availability"] == "unavailable"
    assert payload["unavailable_reason"] == "deny"


def test_run_scrape_marks_unavailable_on_captcha_snapshot(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = data_dir / "scaleai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "index.html"
    snapshot_path.write_text("<html><title>Just a moment...</title>cf_chl_opt</html>" + (" " * 1500), encoding="utf-8")
    providers_path = tmp_path / "providers.json"
    providers_path.write_text(json.dumps(_providers_payload(snapshot_path, mode="snapshot")), encoding="utf-8")

    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    import ji_engine.config as config

    importlib.reload(config)
    run_scrape = importlib.reload(run_scrape_module)

    rc = run_scrape.main(["--providers", "scaleai", "--mode", "SNAPSHOT", "--providers-config", str(providers_path)])
    assert rc == 0
    payload = json.loads((data_dir / "ashby_cache" / "scaleai_scrape_meta.json").read_text(encoding="utf-8"))
    assert payload["availability"] == "unavailable"
    assert payload["unavailable_reason"] == "captcha"


def test_run_scrape_marks_unavailable_on_empty_live_success(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = data_dir / "scaleai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "index.html"
    snapshot_path.write_text(
        Path("tests/fixtures/providers/scaleai/index.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    providers_path = tmp_path / "providers.json"
    providers_path.write_text(json.dumps(_providers_payload(snapshot_path, mode="live")), encoding="utf-8")

    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    import ji_engine.config as config

    importlib.reload(config)
    run_scrape = importlib.reload(run_scrape_module)
    monkeypatch.setattr(
        run_scrape,
        "evaluate_robots_policy",
        lambda _url, provider_id=None: {
            "provider_id": provider_id,
            "host": "jobs.ashbyhq.com",
            "robots_url": "https://jobs.ashbyhq.com/robots.txt",
            "robots_fetched": True,
            "robots_status": 200,
            "robots_allowed": True,
            "allowlist_allowed": True,
            "final_allowed": True,
            "reason": "ok",
            "user_agent": "jobintel-bot/1.0",
            "allowlist_entries": ["*"],
        },
    )
    monkeypatch.setattr(run_scrape.AshbyProvider, "scrape_live", lambda self: [])

    rc = run_scrape.main(["--providers", "scaleai", "--mode", "LIVE", "--providers-config", str(providers_path)])
    assert rc == 0
    payload = json.loads((data_dir / "ashby_cache" / "scaleai_scrape_meta.json").read_text(encoding="utf-8"))
    assert payload["live_result"] == "success"
    assert payload["parsed_job_count"] == 0
    assert payload["availability"] == "unavailable"
    assert payload["unavailable_reason"] == "empty_success"
