from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from scripts.schema_validate import resolve_named_schema_path, validate_payload


def _setup_env(monkeypatch: Any, tmp_path: Path) -> Dict[str, Path]:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    candidate_id = os.environ.get("JOBINTEL_CANDIDATE_ID", "local")
    output_dir = data_dir / "ashby_cache"
    snapshot_dir = data_dir / "openai_snapshots"
    candidate_profile_dir = state_dir / "candidates" / candidate_id / "inputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    candidate_profile_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "index.html").write_text("<html>snapshot</html>", encoding="utf-8")
    (data_dir / "candidate_profile.json").write_text('{"skills": [], "roles": []}', encoding="utf-8")
    (candidate_profile_dir / "candidate_profile.json").write_text('{"skills": [], "roles": []}', encoding="utf-8")
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


def _assert_provider_availability_ui_safe(payload: Dict[str, Any]) -> None:
    from ji_engine.artifacts.catalog import ArtifactCategory, assert_no_forbidden_fields, get_artifact_category

    assert get_artifact_category("provider_availability_v1.json") == ArtifactCategory.UI_SAFE
    assert_no_forbidden_fields(payload, context="provider_availability_v1.json")


def _latest_run_audit_path(run_daily: Any) -> Path:
    roots = [run_daily.candidate_state_paths(run_daily.CANDIDATE_ID).runs]
    if run_daily.CANDIDATE_ID == run_daily.DEFAULT_CANDIDATE_ID:
        roots.append(run_daily.RUN_METADATA_DIR)
    paths = sorted(path for root in roots for path in root.glob("*/artifacts/run_audit_v1.json"))
    assert paths, "run_audit artifact should exist"
    return paths[-1]


def _validate_run_audit_schema(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(resolve_named_schema_path("run_audit", 1).read_text(encoding="utf-8"))
    errors = validate_payload(payload, schema)
    assert errors == [], f"run_audit schema validation failed: {errors}"
    return payload


def _fake_success_run(run_daily: Any, output_dir: Path):
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

    return fake_run


def test_run_health_written_on_success(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _setup_env(monkeypatch, tmp_path)
    output_dir = paths["output_dir"]

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    monkeypatch.setattr(run_daily, "_run", _fake_success_run(run_daily, output_dir))
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    assert run_daily.main() == 0

    payload = _latest_run_health(run_daily)
    _validate_run_health_schema(payload)
    assert payload["status"] == "success"
    assert payload["phases"]["snapshot_fetch"]["status"] == "success"
    assert payload["phases"]["score"]["status"] == "success"
    availability_path = _latest_provider_availability_path(run_daily)
    availability = _validate_provider_availability_schema(availability_path)
    _assert_provider_availability_ui_safe(availability)
    assert availability["run_id"]
    provider_ids = [entry["provider_id"] for entry in availability["providers"]]
    assert provider_ids == sorted(provider_ids)
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers
    assert providers["openai"]["mode"] in {"snapshot", "live", "disabled"}
    audit_path = _latest_run_audit_path(run_daily)
    audit = _validate_run_audit_schema(audit_path)
    assert audit["candidate_id"] == "local"
    assert audit["trigger_type"] == "manual"
    assert isinstance(audit["profile_hash"], str)
    assert audit["profile_hash"]


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
    _assert_provider_availability_ui_safe(availability)
    assert availability["run_id"]
    provider_ids = [entry["provider_id"] for entry in availability["providers"]]
    assert provider_ids == sorted(provider_ids)
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers

    run_reports = sorted(run_daily.RUN_METADATA_DIR.glob("*.json"))
    assert run_reports, "run_report metadata should still be written on controlled failure"
    run_report_payload = json.loads(run_reports[-1].read_text(encoding="utf-8"))
    assert run_report_payload["run_report_schema_version"] == 1
    artifact_pointer = run_report_payload.get("provider_availability_artifact")
    assert isinstance(artifact_pointer, dict)
    assert artifact_pointer.get("path")
    audit_path = _latest_run_audit_path(run_daily)
    audit = _validate_run_audit_schema(audit_path)
    assert audit["candidate_id"] == "local"


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
    """Forced failure still emits provider_availability as a fail-closed artifact."""
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
    availability_path = _latest_provider_availability_path(run_daily)
    availability = _validate_provider_availability_schema(availability_path)
    _assert_provider_availability_ui_safe(availability)
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers
    assert providers["openai"]["availability"] == "unavailable"
    assert providers["openai"]["reason_code"] in {"early_failure_unknown", "policy_denied"}
    audit_path = _latest_run_audit_path(run_daily)
    audit = _validate_run_audit_schema(audit_path)
    assert audit["run_id"] == payload["run_id"]


def test_forced_failure_e2e_artifact_paths(tmp_path: Path, monkeypatch: Any) -> None:
    """E2E: forced failure emits run_health, run_summary, and provider_availability at canonical paths."""
    paths = _setup_env(monkeypatch, tmp_path)
    monkeypatch.setenv("JOBINTEL_FORCE_FAIL_STAGE", "scrape")

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    monkeypatch.setattr(run_daily, "_run", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    rc = run_daily.main()
    assert rc != 0

    run_dirs = sorted(
        (p for p in run_daily.RUN_METADATA_DIR.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )
    assert run_dirs, "run dir should exist"
    run_dir = run_dirs[-1]

    run_health_path = run_dir / "run_health.v1.json"
    run_summary_path = run_dir / "run_summary.v1.json"
    provider_availability_path = run_dir / "artifacts" / "provider_availability_v1.json"

    assert run_health_path.exists(), f"run_health must exist at {run_health_path}"
    assert run_summary_path.exists(), f"run_summary must exist at {run_summary_path}"

    health = json.loads(run_health_path.read_text(encoding="utf-8"))
    summary = json.loads(run_summary_path.read_text(encoding="utf-8"))

    assert health["status"] == "failed"
    assert health["failed_stage"] == "scrape"
    assert "FORCED_FAILURE" in health["failure_codes"]
    assert summary["status"] == "failed"
    assert "run_health" in summary
    assert provider_availability_path.exists(), f"provider_availability must exist at {provider_availability_path}"
    availability = _validate_provider_availability_schema(provider_availability_path)
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers
    assert providers["openai"]["availability"] == "unavailable"
    assert providers["openai"]["reason_code"] == "early_failure_unknown"


def test_provider_availability_written_on_provider_policy_failure(tmp_path: Path, monkeypatch: Any) -> None:
    """Provider policy/network-shield denial still emits provider_availability and run_health."""
    _setup_env(monkeypatch, tmp_path)

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    monkeypatch.setattr(run_daily, "_run", lambda *a, **k: None)
    monkeypatch.setattr(
        run_daily,
        "_load_scrape_provenance",
        lambda providers: {
            "openai": {
                "availability": "unavailable",
                "unavailable_reason": "allowlist_denied",
                "attempts_made": 1,
                "scrape_mode": "live",
                "parsed_job_count": 0,
                "allowlist_allowed": False,
                "robots_final_allowed": False,
                "live_error_reason": "allowlist_denied",
                "live_error_type": "policy",
            }
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_daily.py",
            "--no_subprocess",
            "--providers",
            "openai",
            "--scrape_only",
            "--no_post",
        ],
    )

    rc = run_daily.main()
    assert rc == 3

    payload = _latest_run_health(run_daily)
    _validate_run_health_schema(payload)
    assert payload["status"] == "failed"
    assert payload["failed_stage"] == "provider_policy"
    assert "PROVIDER_POLICY_FAILED" in payload["failure_codes"]

    availability_path = _latest_provider_availability_path(run_daily)
    availability = _validate_provider_availability_schema(availability_path)
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers
    assert providers["openai"]["availability"] == "unavailable"
    assert providers["openai"]["reason_code"] == "policy_denied"
    assert providers["openai"]["policy"]["network_shield"]["allowlist_allowed"] is False


def test_provider_availability_written_when_no_enabled_providers(tmp_path: Path, monkeypatch: Any) -> None:
    """No-enabled-provider startup failure still emits provider_availability and run_health."""
    _setup_env(monkeypatch, tmp_path)
    providers_path = tmp_path / "providers-disabled.json"
    providers_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "providers": [
                    {
                        "provider_id": "openai",
                        "display_name": "OpenAI",
                        "enabled": False,
                        "careers_urls": ["https://jobs.ashbyhq.com/openai"],
                        "extraction_mode": "ashby",
                        "snapshot_path": "data/openai_snapshots/index.html",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_daily.py",
            "--no_subprocess",
            "--profiles",
            "cs",
            "--providers-config",
            str(providers_path),
            "--no_post",
        ],
    )

    rc = run_daily.main()
    assert rc == 2

    payload = _latest_run_health(run_daily)
    _validate_run_health_schema(payload)
    assert payload["status"] == "failed"
    assert payload["failed_stage"] == "startup"

    availability_path = _latest_provider_availability_path(run_daily)
    availability = _validate_provider_availability_schema(availability_path)
    _assert_provider_availability_ui_safe(availability)
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers
    assert providers["openai"]["enabled"] is False
    assert providers["openai"]["availability"] == "unavailable"
    assert providers["openai"]["reason_code"] == "not_enabled"


def test_provider_availability_written_when_primary_and_retry_writers_fail(tmp_path: Path, monkeypatch: Any) -> None:
    """If the primary+retry availability writers raise, deterministic minimal fallback is still emitted."""
    paths = _setup_env(monkeypatch, tmp_path)
    output_dir = paths["output_dir"]

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    monkeypatch.setattr(run_daily, "_run", _fake_success_run(run_daily, output_dir))
    monkeypatch.setattr(
        run_daily,
        "_write_provider_availability_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("simulated availability writer failure")),
    )
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    assert run_daily.main() == 0

    availability_path = _latest_provider_availability_path(run_daily)
    availability = _validate_provider_availability_schema(availability_path)
    _assert_provider_availability_ui_safe(availability)
    providers = {entry["provider_id"]: entry for entry in availability["providers"]}
    assert "openai" in providers
    assert providers["openai"]["availability"] == "unavailable"
    assert providers["openai"]["reason_code"] == "early_failure_unknown"
    assert providers["openai"]["unavailable_reason"] == "fail_closed:unknown_due_to_early_failure"
    assert providers["openai"]["attempts_made"] == 0


def test_run_audit_written_for_non_local_candidate(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("JOBINTEL_CANDIDATE_ID", "alice")
    monkeypatch.setenv("JOBINTEL_RUN_ID", "2026-02-18T00:00:10Z")
    paths = _setup_env(monkeypatch, tmp_path)
    output_dir = paths["output_dir"]
    (paths["state_dir"] / "candidates" / "alice" / "inputs" / "candidate_profile.json").write_text(
        '{"skills": ["python"], "roles": ["csm"]}',
        encoding="utf-8",
    )

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False
    monkeypatch.setattr(run_daily, "_run", _fake_success_run(run_daily, output_dir))
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    assert run_daily.main() == 0

    audit_path = _latest_run_audit_path(run_daily)
    audit = _validate_run_audit_schema(audit_path)
    assert audit["candidate_id"] == "alice"
    assert "/state/candidates/alice/runs/" in audit_path.as_posix()
    assert isinstance(audit["profile_hash"], str)
    assert audit["profile_hash"]


def test_run_audit_no_cross_candidate_leakage(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("JOBINTEL_RUN_ID", "2026-02-18T00:00:11Z")
    # local run
    paths = _setup_env(monkeypatch, tmp_path)
    output_dir = paths["output_dir"]
    (paths["state_dir"] / "candidates" / "local" / "inputs" / "candidate_profile.json").write_text(
        '{"skills": ["local-skill"], "roles": ["local-role"]}',
        encoding="utf-8",
    )

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False
    monkeypatch.setattr(run_daily, "_run", _fake_success_run(run_daily, output_dir))
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])
    assert run_daily.main() == 0
    local_audit_path = _latest_run_audit_path(run_daily)
    local_audit = _validate_run_audit_schema(local_audit_path)
    run_daily.LOCK_PATH.unlink(missing_ok=True)

    # alice run in same workspace/state tree should remain candidate-scoped.
    monkeypatch.setenv("JOBINTEL_CANDIDATE_ID", "alice")
    monkeypatch.setenv("JOBINTEL_RUN_ID", "2026-02-18T00:00:12Z")
    _setup_env(monkeypatch, tmp_path)
    (paths["state_dir"] / "candidates" / "alice" / "inputs" / "candidate_profile.json").write_text(
        '{"skills": ["alice-skill"], "roles": ["alice-role"]}',
        encoding="utf-8",
    )
    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False
    monkeypatch.setattr(run_daily, "_run", _fake_success_run(run_daily, output_dir))
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])
    assert run_daily.main() == 0
    alice_audit_path = _latest_run_audit_path(run_daily)
    alice_audit = _validate_run_audit_schema(alice_audit_path)

    assert local_audit["candidate_id"] == "local"
    assert alice_audit["candidate_id"] == "alice"
    assert local_audit["profile_hash"] != alice_audit["profile_hash"]
    assert "profile_hash_previous" not in alice_audit
    assert "/state/candidates/alice/runs/" in alice_audit_path.as_posix()
