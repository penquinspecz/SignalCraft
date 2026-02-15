from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

from scripts.schema_validate import resolve_named_schema_path, validate_payload


def _setup_env(monkeypatch: Any, tmp_path: Path) -> Dict[str, Path]:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    output_dir = data_dir / "ashby_cache"
    snapshot_dir = data_dir / "openai_snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "index.html").write_text("<html>snapshot</html>", encoding="utf-8")
    (data_dir / "candidate_profile.json").write_text('{"skills": [], "roles": []}', encoding="utf-8")
    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(state_dir))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    return {"data_dir": data_dir, "state_dir": state_dir, "output_dir": output_dir}


def _latest_run_health(run_daily: Any) -> Dict[str, Any]:
    health_files = sorted(run_daily.RUN_METADATA_DIR.glob("*/run_health.v1.json"))
    assert health_files, "run_health artifact should exist"
    return json.loads(health_files[-1].read_text(encoding="utf-8"))


def _validate_run_health_schema(payload: Dict[str, Any]) -> None:
    schema = json.loads(resolve_named_schema_path("run_health", 1).read_text(encoding="utf-8"))
    errors = validate_payload(payload, schema)
    assert errors == [], f"run_health schema validation failed: {errors}"


def _latest_provider_availability_path(run_daily: Any) -> Path:
    paths = sorted(run_daily.RUN_METADATA_DIR.glob("*/artifacts/provider_availability_v1.json"))
    assert paths, "provider availability artifact should exist"
    return paths[-1]


def _validate_provider_availability_schema(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(resolve_named_schema_path("provider_availability", 1).read_text(encoding="utf-8"))
    errors = validate_payload(payload, schema)
    assert errors == [], f"provider_availability schema validation failed: {errors}"
    return payload


def test_run_health_written_on_success(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _setup_env(monkeypatch, tmp_path)
    output_dir = paths["output_dir"]

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    def fake_run(cmd: list[str], *, stage: str) -> None:
        if stage == "scrape":
            (output_dir / "openai_raw_jobs.json").write_text("[]", encoding="utf-8")
        elif stage == "classify":
            (output_dir / "openai_labeled_jobs.json").write_text("[]", encoding="utf-8")
        elif stage == "enrich":
            (output_dir / "openai_enriched_jobs.json").write_text("[]", encoding="utf-8")
        elif stage.startswith("score:"):
            profile = stage.split(":", 1)[1]
            for path in (
                run_daily._provider_ranked_jobs_json("openai", profile),
                run_daily._provider_ranked_jobs_csv("openai", profile),
                run_daily._provider_ranked_families_json("openai", profile),
                run_daily._provider_shortlist_md("openai", profile),
                run_daily._provider_top_md("openai", profile),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix == ".json":
                    path.write_text("[]", encoding="utf-8")
                else:
                    path.write_text("", encoding="utf-8")

    monkeypatch.setattr(run_daily, "_run", fake_run)
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    assert run_daily.main() == 0

    payload = _latest_run_health(run_daily)
    _validate_run_health_schema(payload)
    assert payload["status"] == "success"
    assert payload["phases"]["snapshot_fetch"]["status"] == "success"
    assert payload["phases"]["score"]["status"] == "success"
    availability_path = _latest_provider_availability_path(run_daily)
    availability = _validate_provider_availability_schema(availability_path)
    assert availability["run_id"]
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers
    assert providers["openai"]["mode"] in {"snapshot", "live", "disabled"}


def test_run_health_written_on_controlled_failure(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _setup_env(monkeypatch, tmp_path)
    output_dir = paths["output_dir"]

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    def fake_run(cmd: list[str], *, stage: str) -> None:
        if stage == "scrape":
            (output_dir / "openai_raw_jobs.json").write_text("[]", encoding="utf-8")
            return
        if stage == "classify":
            raise SystemExit(3)

    monkeypatch.setattr(run_daily, "_run", fake_run)
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    rc = run_daily.main()
    assert rc == 3

    payload = _latest_run_health(run_daily)
    _validate_run_health_schema(payload)
    assert payload["status"] == "failed"
    assert payload["failed_stage"] == "classify"
    assert "CLASSIFY_STAGE_FAILED" in payload["failure_codes"]
    availability_path = _latest_provider_availability_path(run_daily)
    availability = _validate_provider_availability_schema(availability_path)
    assert availability["run_id"]
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers

    run_reports = sorted(run_daily.RUN_METADATA_DIR.glob("*.json"))
    assert run_reports, "run_report metadata should still be written on controlled failure"
    run_report_payload = json.loads(run_reports[-1].read_text(encoding="utf-8"))
    assert run_report_payload["run_report_schema_version"] == 1
    artifact_pointer = run_report_payload.get("provider_availability_artifact")
    assert isinstance(artifact_pointer, dict)
    assert artifact_pointer.get("path")


def test_run_health_written_on_forced_failure(tmp_path: Path, monkeypatch: Any) -> None:
    """Forced failure via JOBINTEL_FORCE_FAIL_STAGE emits run_health with failed_stage and FORCED_FAILURE."""
    paths = _setup_env(monkeypatch, tmp_path)
    output_dir = paths["output_dir"]

    monkeypatch.setenv("JOBINTEL_FORCE_FAIL_STAGE", "scrape")

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    def fake_run(cmd: list[str], *, stage: str) -> None:
        if stage == "scrape":
            (output_dir / "openai_raw_jobs.json").write_text("[]", encoding="utf-8")
        elif stage == "classify":
            (output_dir / "openai_labeled_jobs.json").write_text("[]", encoding="utf-8")
        elif stage == "enrich":
            (output_dir / "openai_enriched_jobs.json").write_text("[]", encoding="utf-8")
        elif stage.startswith("score:"):
            profile = stage.split(":", 1)[1]
            for path in (
                run_daily._provider_ranked_jobs_json("openai", profile),
                run_daily._provider_ranked_jobs_csv("openai", profile),
                run_daily._provider_ranked_families_json("openai", profile),
                run_daily._provider_shortlist_md("openai", profile),
                run_daily._provider_top_md("openai", profile),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix == ".json":
                    path.write_text("[]", encoding="utf-8")
                else:
                    path.write_text("", encoding="utf-8")

    monkeypatch.setattr(run_daily, "_run", fake_run)
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    rc = run_daily.main()
    assert rc != 0

    payload = _latest_run_health(run_daily)
    _validate_run_health_schema(payload)
    assert payload["status"] == "failed"
    assert payload["failed_stage"] == "scrape"
    assert "FORCED_FAILURE" in payload["failure_codes"]


def test_provider_availability_on_forced_failure(tmp_path: Path, monkeypatch: Any) -> None:
    """On forced failure, run_health and run_summary are emitted; provider_availability is not a separate
    artifact (fail-closed: runner builds it from provenance, which may be empty on early failure).
    """
    paths = _setup_env(monkeypatch, tmp_path)
    monkeypatch.setenv("JOBINTEL_FORCE_FAIL_STAGE", "classify")

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    output_dir = paths["output_dir"]

    def fake_run(cmd: list[str], *, stage: str) -> None:
        if stage == "scrape":
            (output_dir / "openai_raw_jobs.json").write_text("[]", encoding="utf-8")
        elif stage == "classify":
            pass  # forced fail before _run executes

    monkeypatch.setattr(run_daily, "_run", fake_run)
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    rc = run_daily.main()
    assert rc != 0

    payload = _latest_run_health(run_daily)
    _validate_run_health_schema(payload)
    assert payload["failed_stage"] == "classify"
    assert "FORCED_FAILURE" in payload["failure_codes"]

    run_summaries = sorted(run_daily.RUN_METADATA_DIR.glob("*/run_summary.v1.json"))
    assert run_summaries, "run_summary should be emitted on forced failure"
