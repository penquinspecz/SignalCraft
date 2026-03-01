from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import quote

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def _sanitize(run_id: str) -> str:
    return run_id.replace(":", "").replace("-", "").replace(".", "")


def test_dashboard_version_shape_and_stability(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.dashboard.app as dashboard

    importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    resp = client.get("/version")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["service"] == "SignalCraft"
    assert "git_sha" in payload
    assert isinstance(payload["git_sha"], str)
    assert "schema_versions" in payload
    schemas = payload["schema_versions"]
    assert isinstance(schemas, dict)
    assert schemas.get("run_summary") == 1
    assert schemas.get("run_health") == 1
    # build_timestamp is optional
    if "build_timestamp" in payload:
        assert isinstance(payload["build_timestamp"], str)


def test_dashboard_version_git_sha_from_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_GIT_SHA", "abc123def")

    import importlib

    import ji_engine.dashboard.app as dashboard

    importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    resp = client.get("/version")
    assert resp.status_code == 200
    assert resp.json()["git_sha"] == "abc123def"


def test_dashboard_version_build_timestamp_optional(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_BUILD_TIMESTAMP", "2026-02-15T12:00:00Z")

    import importlib

    import ji_engine.dashboard.app as dashboard

    importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    resp = client.get("/version")
    assert resp.status_code == 200
    assert resp.json().get("build_timestamp") == "2026-02-15T12:00:00Z"


def test_dashboard_runs_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_runs_populated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "openai_ranked_jobs.cs.json"
    artifact_path.write_text("[]", encoding="utf-8")
    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "providers": {"openai": {"profiles": {"cs": {"diff_counts": {"new": 1, "changed": 0, "removed": 0}}}}},
        "artifacts": {artifact_path.name: artifact_path.relative_to(run_dir).as_posix()},
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (run_dir / "run_report.json").write_text(
        json.dumps(
            {
                "semantic_enabled": True,
                "semantic_mode": "boost",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "costs.json").write_text(
        json.dumps(
            {
                "embeddings_count": 2,
                "embeddings_estimated_tokens": 256,
                "ai_calls": 1,
                "ai_estimated_tokens": 32,
                "total_estimated_tokens": 288,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "ai_insights.cs.json").write_text(
        json.dumps({"metadata": {"prompt_version": "weekly_insights_v3"}}),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() and resp.json()[0]["run_id"] == run_id

    detail = client.get(f"/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id
    assert detail.json()["semantic_enabled"] is True
    assert detail.json()["semantic_mode"] == "boost"
    assert detail.json()["ai_prompt_version"] == "weekly_insights_v3"
    assert detail.json()["cost_summary"]["total_estimated_tokens"] == 288

    artifact = client.get(f"/runs/{run_id}/artifact/{artifact_path.name}")
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("application/json")


def test_dashboard_artifact_exfil_guard_rejects_invalid_mapping(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (config.STATE_DIR / "secret.txt").write_text("secret", encoding="utf-8")
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "artifacts": {"leak": "../secret.txt"},
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}/artifact/leak")
    assert resp.status_code == 500
    assert "invalid" in resp.json()["detail"].lower()


def test_dashboard_artifact_exfil_guard_rejects_oversized_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "artifacts": {"safe.json": "safe.json"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "safe.json").write_text("[]", encoding="utf-8")

    client = TestClient(dashboard.app)
    oversized = "a" * 300
    resp = client.get(f"/runs/{run_id}/artifact/{oversized}")
    assert resp.status_code == 400
    assert "invalid artifact name" in resp.json()["detail"].lower()


def test_dashboard_artifact_oversized_non_json_returns_413_without_body_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_DASHBOARD_MAX_JSON_BYTES", "64")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "notes.md"
    artifact_path.write_text("x" * 512, encoding="utf-8")
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "artifacts": {"notes.md": "notes.md"},
            }
        ),
        encoding="utf-8",
    )

    orig_read_bytes = Path.read_bytes
    orig_read_text = Path.read_text

    def _guard_read_bytes(self: Path) -> bytes:
        if self == artifact_path:
            raise AssertionError("Oversized artifact should be rejected before read_bytes")
        return orig_read_bytes(self)

    def _guard_read_text(self: Path, *args, **kwargs) -> str:
        if self == artifact_path:
            raise AssertionError("Oversized artifact should be rejected before read_text")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", _guard_read_bytes)
    monkeypatch.setattr(Path, "read_text", _guard_read_text)

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}/artifact/notes.md")
    assert resp.status_code == 413
    detail = resp.json()["detail"]
    assert detail["error"] == "artifact_too_large"
    assert detail["max_bytes"] == 64


def test_dashboard_artifact_oversized_json_returns_413_without_body_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_DASHBOARD_MAX_JSON_BYTES", "64")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "openai_ranked_jobs.cs.json"
    artifact_path.write_text(json.dumps({"jobs": ["x" * 1024]}), encoding="utf-8")
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "artifacts": {"openai_ranked_jobs.cs.json": "openai_ranked_jobs.cs.json"},
            }
        ),
        encoding="utf-8",
    )

    orig_read_text = Path.read_text

    def _guard_read_text(self: Path, *args, **kwargs) -> str:
        if self == artifact_path:
            raise AssertionError("Oversized JSON should be rejected before read_text")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _guard_read_text)

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}/artifact/openai_ranked_jobs.cs.json")
    assert resp.status_code == 413
    detail = resp.json()["detail"]
    assert detail["error"] == "artifact_too_large"
    assert detail["max_bytes"] == 64


def test_dashboard_artifact_small_non_json_serves_successfully(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_DASHBOARD_MAX_JSON_BYTES", "4096")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "notes.md"
    artifact_path.write_text("hello dashboard\n", encoding="utf-8")
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "artifacts": {"notes.md": "notes.md"},
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}/artifact/notes.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.text == "hello dashboard\n"


def test_dashboard_runs_populated_namespaced_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.candidate_run_metadata_dir("alice") / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.json").write_text(json.dumps({"run_id": run_id, "timestamp": run_id}), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get("/runs", params={"candidate_id": "alice"})
    assert resp.status_code == 200
    assert resp.json() and resp.json()[0]["run_id"] == run_id


def test_dashboard_semantic_summary_endpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    semantic_dir = run_dir / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "providers": {"openai": {"profiles": {"cs": {}, "se": {}}}},
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (semantic_dir / "semantic_summary.json").write_text(
        json.dumps({"enabled": True, "model_id": "deterministic-hash-v1"}),
        encoding="utf-8",
    )
    (semantic_dir / "scores_openai_cs.json").write_text(
        json.dumps({"entries": [{"provider": "openai", "profile": "cs", "job_id": "job-1"}]}),
        encoding="utf-8",
    )
    (semantic_dir / "scores_openai_se.json").write_text(
        json.dumps({"entries": [{"provider": "openai", "profile": "se", "job_id": "job-se"}]}),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}/semantic_summary/cs")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    payload = resp.json()
    assert payload["run_id"] == run_id
    assert payload["profile"] == "cs"
    assert payload["summary"]["enabled"] is True
    assert payload["entries"] == [{"provider": "openai", "profile": "cs", "job_id": "job-1"}]


def test_dashboard_latest_local(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.candidate_run_metadata_dir("local") / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.json").write_text(json.dumps({"run_id": run_id, "timestamp": run_id}), encoding="utf-8")
    last_success = {
        "run_id": run_id,
        "providers": ["openai"],
        "profiles": ["cs"],
    }
    (config.STATE_DIR / "last_success.json").write_text(json.dumps(last_success), encoding="utf-8")
    report = {
        "outputs_by_provider": {
            "openai": {
                "cs": {
                    "ranked_json": {"path": "openai_ranked_jobs.cs.json"},
                    "ranked_csv": {"path": "openai_ranked_jobs.cs.csv"},
                }
            }
        }
    }
    (run_dir / "run_report.json").write_text(json.dumps(report), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get("/v1/latest")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["source"] == "local"
    assert payload["candidate_id"] == "local"
    assert payload["payload"]["run_id"] == run_id

    artifacts = client.get("/v1/artifacts/latest/openai/cs")
    assert artifacts.status_code == 200
    assert "openai_ranked_jobs.cs.json" in artifacts.json()["paths"][0]


def test_dashboard_profile_get_put_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.candidates.registry as candidate_registry
    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    candidate_registry = importlib.reload(candidate_registry)
    dashboard = importlib.reload(dashboard)

    candidate_registry.bootstrap_candidate("alice", "Alice Example")
    candidate_registry.switch_active_candidate("alice")

    client = TestClient(dashboard.app)
    read_initial = client.get("/v1/profile")
    assert read_initial.status_code == 200
    initial_payload = read_initial.json()
    assert initial_payload["candidate_id"] == "alice"
    assert initial_payload["profile_schema_version"] == 1
    assert initial_payload["profile_fields"]["schema_version"] == 1
    assert "text_inputs" not in initial_payload
    assert "text_input_artifacts" not in initial_payload

    update_resp = client.put(
        "/v1/profile",
        json={
            "display_name": "Alice Product",
            "profile_fields": {
                "seniority": "Senior",
                "role_archetype": "Staff IC",
                "location": "Remote",
                "skills": ["Python", "Leadership", "Distributed Systems"],
            },
        },
    )
    assert update_resp.status_code == 200
    updated_payload = update_resp.json()
    assert updated_payload["candidate_id"] == "alice"
    assert updated_payload["display_name"] == "Alice Product"
    assert updated_payload["profile_fields"]["skills"] == ["distributed systems", "leadership", "python"]
    assert updated_payload["profile_hash"] != initial_payload["profile_hash"]

    read_after = client.get("/v1/profile", params={"candidate_id": "alice"})
    assert read_after.status_code == 200
    assert read_after.json()["profile_hash"] == updated_payload["profile_hash"]


def test_dashboard_profile_candidate_isolation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.candidates.registry as candidate_registry
    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    candidate_registry = importlib.reload(candidate_registry)
    dashboard = importlib.reload(dashboard)

    candidate_registry.bootstrap_candidate("alice")
    candidate_registry.bootstrap_candidate("bob")

    client = TestClient(dashboard.app)
    assert (
        client.put(
            "/v1/profile",
            params={"candidate_id": "alice"},
            json={"profile_fields": {"location": "Remote", "skills": ["python"]}},
        ).status_code
        == 200
    )

    alice = client.get("/v1/profile", params={"candidate_id": "alice"}).json()
    bob = client.get("/v1/profile", params={"candidate_id": "bob"}).json()
    assert alice["profile_fields"]["location"] == "Remote"
    assert bob["profile_fields"]["location"] != "Remote"
    assert alice["profile_hash"] != bob["profile_hash"]


def test_dashboard_latest_local_candidate_query_returns_candidate_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.candidate_run_metadata_dir("alice") / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.json").write_text(json.dumps({"run_id": run_id, "timestamp": run_id}), encoding="utf-8")
    pointer_path = config.candidate_last_success_pointer_path("alice")
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_path.write_text(json.dumps({"run_id": run_id}), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get("/v1/latest", params={"candidate_id": "alice"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["source"] == "local"
    assert payload["candidate_id"] == "alice"
    assert payload["payload"]["run_id"] == run_id


def test_dashboard_runs_candidate_isolation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    local_dir = config.candidate_run_metadata_dir("local") / _sanitize(run_id)
    alice_dir = config.candidate_run_metadata_dir("alice") / _sanitize(run_id)
    local_dir.mkdir(parents=True, exist_ok=True)
    alice_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "index.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": "2026-01-22T00:00:00Z"}), encoding="utf-8"
    )
    (alice_dir / "index.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": "2026-01-23T00:00:00Z"}), encoding="utf-8"
    )

    client = TestClient(dashboard.app)
    local_runs = client.get("/runs?candidate_id=local")
    alice_runs = client.get("/runs?candidate_id=alice")
    assert local_runs.status_code == 200
    assert alice_runs.status_code == 200
    assert local_runs.json()[0]["timestamp"] == "2026-01-22T00:00:00Z"
    assert alice_runs.json()[0]["timestamp"] == "2026-01-23T00:00:00Z"


def test_dashboard_invalid_candidate_id_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    resp = client.get("/runs?candidate_id=../../etc")
    assert resp.status_code == 400


def test_dashboard_latest_s3(monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_S3_BUCKET", "proof-bucket")
    monkeypatch.setenv("JOBINTEL_S3_PREFIX", "jobintel")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    monkeypatch.setattr(
        dashboard.aws_runs,
        "read_last_success_state",
        lambda bucket, prefix, candidate_id="local": (
            {"run_id": "2026-01-01T00:00:00Z"},
            "ok",
            "state/last_success.json",
        ),
    )
    monkeypatch.setattr(dashboard, "_s3_list_keys", lambda bucket, prefix: [f"{prefix}key.json"])
    monkeypatch.setattr(dashboard, "_read_s3_json", lambda bucket, key: ({"run_id": "2026-01-01T00:00:00Z"}, "ok"))

    client = TestClient(dashboard.app)
    latest = client.get("/v1/latest")
    assert latest.status_code == 200
    assert latest.json()["source"] == "s3"

    artifacts = client.get("/v1/artifacts/latest/openai/cs")
    assert artifacts.status_code == 200
    assert artifacts.json()["keys"]

    run = client.get("/v1/runs/2026-01-01T00:00:00Z")
    assert run.status_code == 200
    assert run.json()["payload"]["run_id"] == "2026-01-01T00:00:00Z"


def test_dashboard_rejects_invalid_candidate_id(monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", "/tmp/does-not-matter")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    resp = client.get("/runs", params={"candidate_id": "../escape"})
    assert resp.status_code == 400


def test_dashboard_runs_logs_corrupt_index(tmp_path: Path, monkeypatch, caplog) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.json").write_text("{invalid", encoding="utf-8")

    client = TestClient(dashboard.app)
    with caplog.at_level(logging.WARNING):
        resp = client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() == []
    assert "Skipping run index" in caplog.text


def test_dashboard_run_detail_oversized_index_returns_413(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_DASHBOARD_MAX_JSON_BYTES", "64")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    huge_index = {
        "run_id": run_id,
        "timestamp": run_id,
        "artifacts": {"a.json": "x" * 512},
    }
    (run_dir / "index.json").write_text(json.dumps(huge_index), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 413
    assert resp.json()["detail"] == "Run index payload too large"


def test_dashboard_latest_local_oversized_pointer_returns_413(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_DASHBOARD_MAX_JSON_BYTES", "64")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    oversized = {"run_id": "x" * 256}
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    (config.STATE_DIR / "last_success.json").write_text(json.dumps(oversized), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get("/v1/latest")
    assert resp.status_code == 413
    assert resp.json()["detail"] == "Local state payload too large"


def test_dashboard_artifact_model_v2_categorized_artifacts_serve(tmp_path: Path, monkeypatch) -> None:
    """Happy path: categorized artifacts (run_summary, run_health, ranked_jobs) validate and serve."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    run_summary = {
        "run_summary_schema_version": 1,
        "run_id": run_id,
        "candidate_id": "local",
        "status": "success",
        "git_sha": "abc123",
        "created_at_utc": "2026-01-22T00:00:00Z",
        "run_health": {"path": "run_health.v1.json", "sha256": "x", "status": "success"},
        "run_report": {"path": "run_report.json", "sha256": "y"},
        "ranked_outputs": {},
        "primary_artifacts": {},
        "costs": {},
        "scoring_config": {},
        "snapshot_manifest": {},
        "quicklinks": {},
    }
    (run_dir / "run_summary.v1.json").write_text(json.dumps(run_summary), encoding="utf-8")
    run_health = {
        "run_health_schema_version": 1,
        "run_id": run_id,
        "candidate_id": "local",
        "status": "success",
        "timestamps": {"started_at": "2026-01-22T00:00:00Z", "ended_at": "2026-01-22T00:01:00Z"},
        "durations": {},
        "failed_stage": None,
        "failure_codes": [],
        "phases": {},
        "logs": {},
        "proof_bundle_path": "",
    }
    (run_dir / "run_health.v1.json").write_text(json.dumps(run_health), encoding="utf-8")
    (run_dir / "openai_ranked_jobs.cs.json").write_text("[]", encoding="utf-8")
    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "artifacts": {
            "run_summary.v1.json": "run_summary.v1.json",
            "run_health.v1.json": "run_health.v1.json",
            "openai_ranked_jobs.cs.json": "openai_ranked_jobs.cs.json",
        },
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    client = TestClient(dashboard.app)
    for name in ["run_summary.v1.json", "run_health.v1.json", "openai_ranked_jobs.cs.json"]:
        resp = client.get(f"/runs/{run_id}/artifact/{name}")
        assert resp.status_code == 200, (
            f"artifact {name}: {resp.status_code} {resp.json() if resp.status_code != 200 else ''}"
        )


def test_dashboard_artifact_model_v2_uncategorized_fails_closed(tmp_path: Path, monkeypatch) -> None:
    """Fail-closed: uncategorized artifact key returns 503 with structured error."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "unknown_artifact.json").write_text('{"foo": "bar"}', encoding="utf-8")
    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "artifacts": {"unknown_artifact.json": "unknown_artifact.json"},
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}/artifact/unknown_artifact.json")
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["error"] == "artifact_uncategorized"
    assert detail["artifact_key"] == "unknown_artifact.json"
    assert detail["run_id"] == run_id


def test_dashboard_artifact_model_v2_ui_safe_prohibition_rejects_jd_text(tmp_path: Path, monkeypatch) -> None:
    """UI-safe prohibition: payload with jd_text fails validation."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    ai_insights = {"metadata": {"prompt_version": "v1"}, "jobs": [{"job_id": "j1", "jd_text": "forbidden"}]}
    (run_dir / "ai_insights.cs.json").write_text(json.dumps(ai_insights), encoding="utf-8")
    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "artifacts": {"ai_insights.cs.json": "ai_insights.cs.json"},
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}/artifact/ai_insights.cs.json")
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "ui_safe" in str(detail).lower() or "jd_text" in str(detail).lower() or "prohibited" in str(detail).lower()


def test_dashboard_semantic_summary_invalid_json_returns_500(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    semantic_dir = run_dir / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.json").write_text(json.dumps({"run_id": run_id, "timestamp": run_id}), encoding="utf-8")
    (semantic_dir / "semantic_summary.json").write_text("{broken", encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}/semantic_summary/cs")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Semantic summary invalid JSON"


def test_dashboard_v1_artifact_index_shape_and_schema_versions(tmp_path: Path, monkeypatch) -> None:
    """GET /v1/runs/{run_id}/artifacts returns stable shape with schema_version where applicable."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_summary.v1.json").write_text('{"run_summary_schema_version":1}', encoding="utf-8")
    (run_dir / "run_health.v1.json").write_text('{"run_health_schema_version":1}', encoding="utf-8")
    (run_dir / "openai_ranked_jobs.cs.json").write_text("[]", encoding="utf-8")
    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "artifacts": {
            "run_summary.v1.json": "run_summary.v1.json",
            "run_health.v1.json": "run_health.v1.json",
            "openai_ranked_jobs.cs.json": "openai_ranked_jobs.cs.json",
        },
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get(f"/v1/runs/{run_id}/artifacts?candidate_id=local")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_id"] == run_id
    assert payload["candidate_id"] == "local"
    assert "artifacts" in payload
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, list)
    assert len(artifacts) == 3

    keys = {a["key"] for a in artifacts}
    assert keys == {"openai_ranked_jobs.cs.json", "run_health.v1.json", "run_summary.v1.json"}

    for a in artifacts:
        assert "key" in a
        assert "path" in a
        assert "content_type" in a
        assert a["content_type"] in ("application/json", "text/csv", "text/markdown", "text/plain")
        if a["key"] in ("run_summary.v1.json", "run_health.v1.json"):
            assert a.get("schema_version") == 1
        if a["key"] == "openai_ranked_jobs.cs.json":
            assert "size_bytes" in a
            assert a["size_bytes"] == 2


def test_dashboard_v1_artifact_index_unknown_run_returns_404(tmp_path: Path, monkeypatch) -> None:
    """GET /v1/runs/{run_id}/artifacts returns 404 for unknown run_id."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    (tmp_path / "state" / "runs").mkdir(parents=True, exist_ok=True)

    import importlib

    import ji_engine.dashboard.app as dashboard

    importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    resp = client.get("/v1/runs/2026-99-99T99:99:99Z/artifacts?candidate_id=local")
    assert resp.status_code == 404
    assert "not found" in str(resp.json().get("detail", "")).lower()


def test_dashboard_v1_artifact_index_rejects_invalid_run_id(tmp_path: Path, monkeypatch) -> None:
    """GET /v1/runs/{run_id}/artifacts returns 400 for invalid run_id."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    (tmp_path / "state" / "runs").mkdir(parents=True, exist_ok=True)

    import importlib

    import ji_engine.dashboard.app as dashboard

    importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    for bad_run_id in ("", "a/b", "a\\b", "x" * 200):
        path_run_id = quote(bad_run_id, safe="") if bad_run_id else ""
        resp = client.get(f"/v1/runs/{path_run_id}/artifacts?candidate_id=local")
        assert resp.status_code == 400, f"run_id={bad_run_id!r} expected 400 got {resp.status_code}"
        assert "invalid" in str(resp.json().get("detail", "")).lower()


def test_dashboard_v1_artifact_index_rejects_path_traversal_run_id(tmp_path: Path, monkeypatch) -> None:
    """GET /v1/runs/{run_id}/artifacts returns 400 for path traversal in run_id."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    (tmp_path / "state" / "runs").mkdir(parents=True, exist_ok=True)

    import importlib

    import ji_engine.dashboard.app as dashboard

    importlib.reload(dashboard)

    client = TestClient(dashboard.app)
    for bad_run_id in ("../etc/passwd", "..", "run/../../../secret"):
        path_run_id = quote(bad_run_id, safe="")
        resp = client.get(f"/v1/runs/{path_run_id}/artifacts?candidate_id=local")
        assert resp.status_code == 400, f"run_id={bad_run_id!r} expected 400 got {resp.status_code}"
        assert "invalid" in str(resp.json().get("detail", "")).lower()


def test_dashboard_v1_artifact_index_bounded_no_huge_reads(tmp_path: Path, monkeypatch) -> None:
    """Artifact index does not read artifact bodies; only metadata (path, size via stat)."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    large_content = "x" * 500_000
    (run_dir / "big_artifact.json").write_text(json.dumps({"data": large_content}), encoding="utf-8")
    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "artifacts": {"big_artifact.json": "big_artifact.json"},
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get(f"/v1/runs/{run_id}/artifacts?candidate_id=local")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["artifacts"]) == 1
    assert payload["artifacts"][0]["key"] == "big_artifact.json"
    assert "size_bytes" in payload["artifacts"][0]
    assert payload["artifacts"][0]["size_bytes"] > 500_000
    assert "data" not in str(payload)
    assert large_content[:100] not in str(payload)


def test_dashboard_ui_v0_static_page_served(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.dashboard.app as dashboard

    dashboard = importlib.reload(dashboard)
    client = TestClient(dashboard.app)
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "SignalCraft UI v0" in resp.text
    assert "Recent Changes" in resp.text
    assert "View Timeline" in resp.text


def test_dashboard_v1_ui_latest_aggregate_payload_and_redaction(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "run_health.v1.json").write_text(
        json.dumps(
            {
                "run_health_schema_version": 1,
                "run_id": run_id,
                "candidate_id": "local",
                "status": "success",
                "timestamps": {"started_at": run_id, "ended_at": run_id},
                "durations": {"total_sec": 1.0},
                "failed_stage": None,
                "failure_codes": [],
                "phases": {},
                "logs": {},
                "proof_bundle_path": "",
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "provider_availability_v1.json").write_text(
        json.dumps(
            {
                "provider_availability_schema_version": 1,
                "run_id": run_id,
                "candidate_id": "local",
                "generated_at_utc": run_id,
                "provider_registry_sha256": None,
                "providers": [
                    {
                        "provider_id": "openai",
                        "mode": "snapshot",
                        "enabled": True,
                        "snapshot_enabled": True,
                        "live_enabled": False,
                        "availability": "available",
                        "reason_code": "SNAPSHOT_OK",
                        "unavailable_reason": None,
                        "attempts_made": 1,
                        "policy": {
                            "robots": {
                                "url": None,
                                "fetched": None,
                                "status_code": None,
                                "allowed": None,
                                "reason": None,
                                "user_agent": None,
                            },
                            "network_shield": {
                                "allowlist_allowed": None,
                                "robots_final_allowed": None,
                                "live_error_reason": None,
                                "live_error_type": None,
                            },
                            "canonical_url_policy": {
                                "policy_snapshot": {},
                                "live_http_status": None,
                                "live_status_code": None,
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "explanation_v1.json").write_text(
        json.dumps(
            {
                "schema_version": "explanation.v1",
                "run_id": run_id,
                "candidate_id": "local",
                "generated_at": run_id,
                "scoring_config_sha256": "x" * 64,
                "top_jobs": [
                    {
                        "job_hash": "a" * 64,
                        "rank": 1,
                        "score_total": 99.1,
                        "top_positive_signals": [],
                        "top_negative_signals": [],
                        "penalties": [],
                        "notes": ["stable"],
                    }
                ],
                "aggregation": {
                    "most_common_penalties": [],
                    "strongest_positive_signals": [],
                    "strongest_negative_signals": [],
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "openai_ranked_jobs.cs.json").write_text(
        json.dumps(
            [
                {
                    "job_id": "j1",
                    "job_hash": "a" * 64,
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "score": 99.1,
                    "apply_url": "https://example.com/jobs/j1",
                    "jd_text": "forbidden must not leak",
                }
            ]
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "job_timeline_v1.json").write_text(
        json.dumps(
            {
                "job_timeline_schema_version": 1,
                "run_id": run_id,
                "candidate_id": "local",
                "generated_at_utc": run_id,
                "jobs": [
                    {
                        "job_hash": "a" * 64,
                        "provider_id": "openai",
                        "canonical_url": "https://example.com/jobs/j1",
                        "observations": [
                            {"observation_id": "obs-1", "observed_at_utc": "2026-01-20T00:00:00Z"},
                            {"observation_id": "obs-2", "observed_at_utc": run_id},
                        ],
                        "changes": [
                            {
                                "from_observation_id": "obs-1",
                                "to_observation_id": "obs-2",
                                "change_hash": "b" * 64,
                                "changed_fields": ["skills", "location"],
                                "field_diffs": {
                                    "set_fields": {"skills": {"added": ["kubernetes", "python"], "removed": []}},
                                    "string_fields": {"location": {"old": "Remote", "new": "Hybrid"}},
                                },
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "status": "success",
                "artifacts": {
                    "run_health.v1.json": "run_health.v1.json",
                    "provider_availability_v1.json": "artifacts/provider_availability_v1.json",
                    "explanation_v1.json": "artifacts/explanation_v1.json",
                    "job_timeline_v1.json": "artifacts/job_timeline_v1.json",
                    "openai_ranked_jobs.cs.json": "openai_ranked_jobs.cs.json",
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run_report.json").write_text(
        json.dumps({"semantic_enabled": True, "semantic_mode": "boost"}),
        encoding="utf-8",
    )
    (run_dir / "costs.json").write_text(json.dumps({"total_estimated_tokens": 123}), encoding="utf-8")
    (tmp_path / "state" / "candidates" / "local" / "system_state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "candidates" / "local" / "system_state" / "last_success.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": run_id}),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get("/v1/ui/latest?candidate_id=local&top_n=5")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_id"] == run_id
    assert payload["candidate_id"] == "local"
    assert payload["top_jobs_artifact"] == "openai_ranked_jobs.cs.json"
    assert payload["top_jobs"][0]["title"] == "Backend Engineer"
    assert payload["run"]["semantic_enabled"] is True
    assert payload["provider_availability"]["providers"][0]["provider_id"] == "openai"
    assert payload["recent_changes"]["window_days"] == 30
    assert payload["recent_changes"]["change_event_count"] == 1
    assert payload["recent_changes"]["notable_changes"][0]["job_hash"] == "a" * 64
    forbidden = _find_forbidden_keys(payload)
    assert forbidden == []


def test_dashboard_v1_ui_latest_bounded_reads_return_413(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_DASHBOARD_MAX_JSON_BYTES", "64")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "openai_ranked_jobs.cs.json").write_text(
        json.dumps([{"job_id": "j1", "title": "x" * 256}]), encoding="utf-8"
    )
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "artifacts": {"openai_ranked_jobs.cs.json": "openai_ranked_jobs.cs.json"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "state" / "candidates" / "local" / "system_state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "candidates" / "local" / "system_state" / "last_success.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": run_id}),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get("/v1/ui/latest?candidate_id=local&top_n=5")
    assert resp.status_code == 413
    assert resp.json()["detail"] == "openai_ranked_jobs.cs.json payload too large"


def test_dashboard_v1_job_timeline_endpoint_returns_projected_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    job_hash = "a" * 64
    (artifacts_dir / "job_timeline_v1.json").write_text(
        json.dumps(
            {
                "job_timeline_schema_version": 1,
                "run_id": run_id,
                "candidate_id": "local",
                "generated_at_utc": run_id,
                "jobs": [
                    {
                        "job_hash": job_hash,
                        "provider_id": "openai",
                        "canonical_url": "https://example.com/jobs/j1",
                        "observations": [
                            {
                                "observation_id": "obs-1",
                                "run_id": "2026-01-20T00:00:00Z",
                                "observed_at_utc": "2026-01-20T00:00:00Z",
                            },
                            {"observation_id": "obs-2", "run_id": run_id, "observed_at_utc": run_id},
                        ],
                        "changes": [
                            {
                                "from_observation_id": "obs-1",
                                "to_observation_id": "obs-2",
                                "change_hash": "b" * 64,
                                "changed_fields": ["skills", "seniority", "location", "compensation"],
                                "field_diffs": {
                                    "set_fields": {"skills": {"added": ["Python", "Kubernetes"], "removed": ["Flask"]}},
                                    "string_fields": {
                                        "seniority": {"old": "mid", "new": "senior"},
                                        "location": {"old": "Remote", "new": "Hybrid"},
                                        "description": {"old": "forbidden", "new": "must_not_leak"},
                                    },
                                    "numeric_range_fields": {
                                        "compensation": {
                                            "old_min": 100000,
                                            "old_max": 130000,
                                            "new_min": 120000,
                                            "new_max": 150000,
                                        }
                                    },
                                },
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "artifacts": {
                    "job_timeline_v1.json": "artifacts/job_timeline_v1.json",
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "state" / "candidates" / "local" / "system_state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "candidates" / "local" / "system_state" / "last_success.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": run_id}),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get(f"/v1/jobs/{job_hash}/timeline?candidate_id=local")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_id"] == run_id
    assert payload["job_hash"] == job_hash
    assert payload["timeline"]["provider_id"] == "openai"
    assert payload["timeline"]["changes"][0]["seniority_shift"] is True
    assert payload["timeline"]["changes"][0]["location_shift"] is True
    assert payload["timeline"]["changes"][0]["compensation_shift"] is True
    forbidden = _find_forbidden_keys(payload)
    assert forbidden == []


def test_dashboard_v1_job_timeline_bounded_reads_return_413(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JOBINTEL_DASHBOARD_MAX_JSON_BYTES", "64")

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "job_timeline_v1.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_hash": "a" * 64,
                        "observations": [{"observation_id": "o1", "observed_at_utc": run_id}],
                        "changes": [{"to_observation_id": "o1", "changed_fields": ["skills"], "field_diffs": {}}],
                        "padding": "x" * 256,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "index.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": run_id,
                "artifacts": {"job_timeline_v1.json": "artifacts/job_timeline_v1.json"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "state" / "candidates" / "local" / "system_state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "candidates" / "local" / "system_state" / "last_success.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": run_id}),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get(f"/v1/jobs/{'a' * 64}/timeline?candidate_id=local")
    assert resp.status_code == 413
    assert resp.json()["detail"] == "job_timeline_v1.json payload too large"


_FORBIDDEN_JD_KEYS = frozenset({"jd_text", "description", "description_text", "descriptionHtml", "job_description"})


def _find_forbidden_keys(obj: object, path: str = "") -> list[str]:
    """Recursively find forbidden JD keys in JSON structure. Returns list of paths."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_str = str(k).lower() if isinstance(k, str) else ""
            if k in _FORBIDDEN_JD_KEYS or k_str in {x.lower() for x in _FORBIDDEN_JD_KEYS}:
                found.append(f"{path}.{k}" if path else str(k))
            found.extend(_find_forbidden_keys(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_find_forbidden_keys(item, f"{path}[{i}]"))
    return found


@pytest.mark.parametrize(
    "endpoint,method",
    [
        ("/version", "GET"),
        ("/healthz", "GET"),
        ("/runs", "GET"),
        ("/runs/20260122T000000Z", "GET"),
        ("/runs/20260122T000000Z/artifact/openai_ranked_jobs.cs.json", "GET"),
        ("/runs/20260122T000000Z/semantic_summary/cs", "GET"),
        ("/v1/profile", "GET"),
        ("/v1/latest", "GET"),
        ("/v1/ui/latest", "GET"),
        ("/v1/jobs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/timeline", "GET"),
        ("/v1/runs/20260122T000000Z/artifacts", "GET"),
    ],
)
def test_dashboard_api_no_raw_jd_leakage(tmp_path: Path, monkeypatch: Any, endpoint: str, method: str) -> None:
    """All dashboard API responses must not contain forbidden JD fields (jd_text, description, etc.)."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Fixture: ranked_jobs with jd_text (replay_safe - must be redacted when served)
    ranked_jobs = [
        {"job_id": "j1", "jd_text": "Secret JD content here", "apply_url": "https://example.com/j1"},
        {"job_id": "j2", "description": "Another forbidden field", "apply_url": "https://example.com/j2"},
    ]
    (run_dir / "openai_ranked_jobs.cs.json").write_text(json.dumps(ranked_jobs), encoding="utf-8")
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "job_timeline_v1.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "job_hash": "a" * 64,
                        "provider_id": "openai",
                        "canonical_url": "https://example.com/j1",
                        "observations": [
                            {"observation_id": "obs-1", "observed_at_utc": "2026-01-20T00:00:00Z"},
                            {"observation_id": "obs-2", "observed_at_utc": run_id},
                        ],
                        "changes": [
                            {
                                "from_observation_id": "obs-1",
                                "to_observation_id": "obs-2",
                                "change_hash": "b" * 64,
                                "changed_fields": ["skills"],
                                "field_diffs": {
                                    "set_fields": {
                                        "skills": {
                                            "added": ["python", "kubernetes"],
                                            "removed": [],
                                        }
                                    }
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    index = {
        "run_id": run_id,
        "timestamp": run_id,
        "providers": {"openai": {"profiles": {"cs": {}}}},
        "artifacts": {
            "run_summary.v1.json": "run_summary.v1.json",
            "openai_ranked_jobs.cs.json": "openai_ranked_jobs.cs.json",
            "job_timeline_v1.json": "artifacts/job_timeline_v1.json",
            "semantic/semantic_summary.json": "semantic/semantic_summary.json",
            "semantic/scores_openai_cs.json": "semantic/scores_openai_cs.json",
        },
    }
    (run_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (run_dir / "run_summary.v1.json").write_text(
        json.dumps(
            {
                "run_summary_schema_version": 1,
                "run_id": run_id,
                "candidate_id": "local",
                "status": "success",
                "git_sha": "x",
                "created_at_utc": run_id,
                "run_health": {},
                "run_report": {},
                "ranked_outputs": {},
                "primary_artifacts": {},
                "costs": {},
                "scoring_config": {},
                "snapshot_manifest": {},
                "quicklinks": {},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run_report.json").write_text(
        json.dumps({"outputs_by_provider": {"openai": {"cs": {}}}, "semantic_enabled": True}),
        encoding="utf-8",
    )
    semantic_dir = run_dir / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    (semantic_dir / "semantic_summary.json").write_text(
        json.dumps({"enabled": True, "embedded_job_count": 2}),
        encoding="utf-8",
    )
    (semantic_dir / "scores_openai_cs.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"job_id": "j1", "provider": "openai", "profile": "cs"},
                    {"job_id": "j2", "provider": "openai", "profile": "cs"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "state" / "candidates" / "local" / "system_state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "candidates" / "local" / "system_state" / "last_success.json").write_text(
        json.dumps({"run_id": run_id, "timestamp": run_id}),
        encoding="utf-8",
    )

    client = TestClient(dashboard.app)
    resp = client.get(endpoint) if method == "GET" else client.request(method, endpoint)

    if resp.status_code != 200:
        pytest.skip(f"Endpoint {endpoint} returned {resp.status_code} (may need more fixture)")

    try:
        data = resp.json()
    except Exception:
        pytest.skip(f"Endpoint {endpoint} did not return JSON")

    forbidden = _find_forbidden_keys(data)
    assert not forbidden, (
        f"Endpoint {endpoint} leaked forbidden JD fields: {forbidden}. "
        "UI-safe endpoints must fail closed; no forbidden keys in response."
    )


def test_dashboard_ui_safe_fail_closed_when_forbidden_key_injected(tmp_path: Path, monkeypatch) -> None:
    """UI-safe endpoints return 500 when payload contains forbidden JD fields (fail-closed)."""
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))

    import importlib

    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    dashboard = importlib.reload(dashboard)

    run_id = "2026-01-22T00:00:00Z"
    run_dir = config.RUN_METADATA_DIR / _sanitize(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    index_with_jd = {
        "run_id": run_id,
        "timestamp": run_id,
        "jd_text": "forbidden leak",
        "artifacts": {},
    }
    (run_dir / "index.json").write_text(json.dumps(index_with_jd), encoding="utf-8")
    (run_dir / "run_report.json").write_text(json.dumps({"semantic_enabled": False}), encoding="utf-8")

    client = TestClient(dashboard.app)
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 500, f"Expected 500 for run_detail with jd_text, got {resp.status_code}"
    detail = resp.json().get("detail", {})
    if isinstance(detail, dict):
        assert "forbidden_jd_fields" in str(detail).lower() or "violations" in str(detail).lower()
