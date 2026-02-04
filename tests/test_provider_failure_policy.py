from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import ji_engine.config as config
import scripts.run_daily as run_daily_module


def test_provider_policy_live_zero_jobs_fails(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    data_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    snapshot = data_dir / "openai_snapshots" / "index.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("snapshot", encoding="utf-8")

    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(state_dir))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    importlib.reload(config)
    run_daily = importlib.reload(run_daily_module)

    def fake_run(cmd, *, stage: str):
        return None

    def fake_provenance(_providers):
        return {
            "openai": {
                "provider": "openai",
                "provider_id": "openai",
                "scrape_mode": "live",
                "parsed_job_count": 0,
                "attempts_made": 1,
                "live_attempted": True,
            }
        }

    monkeypatch.setattr(run_daily, "_run", fake_run)
    monkeypatch.setattr(run_daily, "_load_scrape_provenance", fake_provenance)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_daily.py", "--no_subprocess", "--scrape_only", "--providers", "openai", "--profiles", "cs"],
    )

    rc = run_daily.main()
    assert rc == 3

    metadata_files = sorted(run_daily.RUN_METADATA_DIR.glob("*.json"))
    assert metadata_files
    report = json.loads(metadata_files[-1].read_text(encoding="utf-8"))
    policy = report["provenance_by_provider"]["openai"]["failure_policy"]
    assert policy["decision"] == "fail"
    assert policy["min_jobs"] >= 1
    assert "error_rate_max" in policy
