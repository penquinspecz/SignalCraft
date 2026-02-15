import json
import types

import pytest

from jobintel import cli


def test_cli_run_forwards_flags(monkeypatch):
    captured = {}

    def fake_run(cmd, env=None, check=False, text=False, capture_output=False):
        captured["cmd"] = cmd
        captured["env"] = env
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_validate_candidate_for_run", lambda _: "local")

    rc = cli.main(
        [
            "run",
            "--offline",
            "--role",
            "cs",
            "--providers",
            "openai",
            "--no_post",
            "--no_enrich",
        ]
    )

    assert rc == 0
    cmd = captured["cmd"]
    assert "--profiles" in cmd
    assert "cs" in cmd
    assert "--providers" in cmd
    assert "openai" in cmd
    assert "--offline" in cmd
    assert "--no_post" in cmd
    assert "--no_enrich" in cmd


def test_cli_run_accepts_hyphen_aliases(monkeypatch):
    captured = {}

    def fake_run(cmd, env=None, check=False, text=False, capture_output=False):
        captured["cmd"] = cmd
        captured["env"] = env
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_validate_candidate_for_run", lambda _: "local")

    rc = cli.main(
        [
            "run",
            "--offline",
            "--role",
            "cs",
            "--providers",
            "openai",
            "--no-post",
            "--no-enrich",
        ]
    )

    assert rc == 0
    cmd = captured["cmd"]
    assert "--no_post" in cmd
    assert "--no_enrich" in cmd


def test_cli_run_daily_sets_candidate_id_env(monkeypatch):
    captured = {}

    def fake_run(cmd, env=None, check=False, text=False, capture_output=False):
        captured["cmd"] = cmd
        captured["env"] = env
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_validate_candidate_for_run", lambda _: "alice")

    rc = cli.main(["run", "daily", "--profiles", "cs", "--candidate-id", "alice"])

    assert rc == 0
    assert captured["env"]["JOBINTEL_CANDIDATE_ID"] == "alice"
    assert "--profiles" in captured["cmd"]
    assert "cs" in captured["cmd"]


def test_cli_run_daily_candidate_validation_failure(monkeypatch):
    monkeypatch.setattr(
        cli, "_validate_candidate_for_run", lambda _: (_ for _ in ()).throw(SystemExit("bad candidate"))
    )
    with pytest.raises(SystemExit, match="bad candidate"):
        cli.main(["run", "daily", "--profiles", "cs", "--candidate-id", "BAD"])


def test_cli_run_daily_prints_run_summary_path_when_present(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    run_id = "2026-02-14T16:55:01Z"
    run_summary_path = state_dir / "runs" / "20260214T165501Z" / "run_summary.v1.json"
    run_summary_path.parent.mkdir(parents=True, exist_ok=True)
    run_summary_path.write_text(
        json.dumps(
            {
                "status": "success",
                "run_summary_schema_version": 1,
                "primary_artifacts": [
                    {"path": "state/runs/20260214T165501Z/openai/cs/openai_ranked_jobs.cs.json"},
                    {"path": "state/runs/20260214T165501Z/openai/cs/openai_ranked_jobs.cs.csv"},
                    {"path": "state/runs/20260214T165501Z/openai/cs/openai_shortlist.cs.md"},
                ],
            }
        ),
        encoding="utf-8",
    )
    run_health_path = run_summary_path.parent / "run_health.v1.json"
    run_health_path.write_text('{"status":"success"}', encoding="utf-8")

    monkeypatch.setattr(cli, "_validate_candidate_for_run", lambda _: "local")
    monkeypatch.setattr(cli, "RUN_METADATA_DIR", state_dir / "runs")
    monkeypatch.setattr(cli, "candidate_run_metadata_dir", lambda _: state_dir / "candidates" / "local" / "runs")

    def fake_run(cmd, env=None, check=False, text=False, capture_output=False):
        return types.SimpleNamespace(returncode=0, stdout=f"JOBINTEL_RUN_ID={run_id}\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli.main(["run", "daily", "--profiles", "cs", "--candidate-id", "local"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "RUN_RECEIPT_BEGIN" in out
    assert f"run_id={run_id}" in out
    assert f"run_dir={run_summary_path.parent}" in out
    assert f"run_summary={run_summary_path}" in out
    assert f"run_health={run_health_path}" in out
    assert "primary_artifact_1=" in out
    assert "primary_artifact_2=" in out
    assert "primary_artifact_3=" in out
    assert "RUN_RECEIPT_END" in out
    assert f"RUN_SUMMARY_PATH={run_summary_path}" in out


def test_cli_run_daily_run_receipt_on_partial_or_failed(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    run_id = "2026-02-14T16:55:01Z"
    run_dir = state_dir / "runs" / "20260214T165501Z"
    run_summary_path = run_dir / "run_summary.v1.json"
    run_health_path = run_dir / "run_health.v1.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_summary_path.write_text(
        json.dumps({"status": "failed", "run_summary_schema_version": 1, "primary_artifacts": []}),
        encoding="utf-8",
    )
    run_health_path.write_text('{"status":"failed"}', encoding="utf-8")

    monkeypatch.setattr(cli, "_validate_candidate_for_run", lambda _: "local")
    monkeypatch.setattr(cli, "RUN_METADATA_DIR", state_dir / "runs")
    monkeypatch.setattr(cli, "candidate_run_metadata_dir", lambda _: state_dir / "candidates" / "local" / "runs")

    def fake_run(cmd, env=None, check=False, text=False, capture_output=False):
        return types.SimpleNamespace(returncode=2, stdout=f"JOBINTEL_RUN_ID={run_id}\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli.main(["run", "daily", "--profiles", "cs", "--candidate-id", "local"])
    assert rc == 2
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line]
    receipt_start = lines.index("RUN_RECEIPT_BEGIN")
    assert lines[receipt_start + 1] == f"run_id={run_id}"
    assert lines[receipt_start + 2] == f"run_dir={run_dir}"
    assert lines[receipt_start + 3] == "status=failed"
    assert lines[receipt_start + 4] == f"run_summary={run_summary_path}"
    assert lines[receipt_start + 5] == f"run_health={run_health_path}"
    assert lines[receipt_start + 6] == "RUN_RECEIPT_END"
    assert "RUN_SUMMARY_PATH=" not in out


def test_cli_run_daily_receipt_does_not_print_raw_text(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    run_id = "2026-02-14T16:55:01Z"
    run_summary_path = state_dir / "runs" / "20260214T165501Z" / "run_summary.v1.json"
    run_summary_path.parent.mkdir(parents=True, exist_ok=True)
    run_summary_path.write_text(
        json.dumps(
            {
                "status": "success",
                "run_summary_schema_version": 1,
                "resume_text": "TOP_SECRET_RESUME_TEXT",
                "primary_artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_validate_candidate_for_run", lambda _: "local")
    monkeypatch.setattr(cli, "RUN_METADATA_DIR", state_dir / "runs")
    monkeypatch.setattr(cli, "candidate_run_metadata_dir", lambda _: state_dir / "candidates" / "local" / "runs")

    def fake_run(cmd, env=None, check=False, text=False, capture_output=False):
        return types.SimpleNamespace(returncode=0, stdout=f"JOBINTEL_RUN_ID={run_id}\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli.main(["run", "daily", "--profiles", "cs", "--candidate-id", "local"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "TOP_SECRET_RESUME_TEXT" not in out
    assert f"RUN_SUMMARY_PATH={run_summary_path}" in out


def test_cli_runs_list_prints_stable_table(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "list_runs_as_dicts",
        lambda candidate_id, limit: [
            {
                "run_id": "2026-02-14T16:55:02Z",
                "candidate_id": "local",
                "status": "success",
                "created_at": "2026-02-14T16:55:02Z",
                "summary_path": "state/runs/20260214T165502Z/run_summary.v1.json",
                "health_path": "state/runs/20260214T165502Z/run_health.v1.json",
                "git_sha": "abc123",
            },
            {
                "run_id": "2026-02-14T16:55:01Z",
                "candidate_id": "local",
                "status": "failed",
                "created_at": "2026-02-14T16:55:01Z",
                "summary_path": "state/runs/20260214T165501Z/run_summary.v1.json",
                "health_path": "state/runs/20260214T165501Z/run_health.v1.json",
                "git_sha": "def456",
            },
        ],
    )
    rc = cli.main(["runs", "list", "--candidate-id", "local", "--limit", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line]
    assert lines[0].startswith("RUN_ID")
    assert "CANDIDATE" in lines[0]
    assert "SUMMARY_PATH" in lines[0]
    assert "HEALTH_PATH" in lines[0]
    assert "GIT_SHA" in lines[0]
    assert lines[2].startswith("2026-02-14T16:55:02Z")
    assert lines[3].startswith("2026-02-14T16:55:01Z")
    assert lines[-1] == "ROWS=2"


def test_cli_runs_show_prints_deterministic_receipt(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    run_id = "2026-02-14T16:55:01Z"
    run_dir = state_dir / "runs" / "20260214T165501Z"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_summary_path = run_dir / "run_summary.v1.json"
    run_health_path = run_dir / "run_health.v1.json"
    run_summary_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "success",
                "git_sha": "abc123",
                "created_at_utc": run_id,
                "primary_artifacts": [
                    {"artifact_key": "ranked_json", "path": "state/runs/20260214T165501Z/openai/cs/a.json"},
                    {"artifact_key": "ranked_csv", "path": "state/runs/20260214T165501Z/openai/cs/a.csv"},
                    {"artifact_key": "shortlist_md", "path": "state/runs/20260214T165501Z/openai/cs/a.md"},
                ],
            }
        ),
        encoding="utf-8",
    )
    run_health_path.write_text(json.dumps({"status": "success"}), encoding="utf-8")

    monkeypatch.setattr(cli, "RUN_METADATA_DIR", state_dir / "runs")
    monkeypatch.setattr(cli, "candidate_run_metadata_dir", lambda _: state_dir / "candidates" / "local" / "runs")
    monkeypatch.setattr(
        cli,
        "get_run_as_dict",
        lambda run_id, candidate_id: {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "status": "success",
            "created_at": "2026-02-14T16:55:01Z",
            "git_sha": "abc123",
            "summary_path": str(run_summary_path),
            "health_path": str(run_health_path),
        },
    )

    rc = cli.main(["runs", "show", run_id, "--candidate-id", "local"])
    assert rc == 0
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line]
    assert lines[0] == "RUN_SHOW_BEGIN"
    assert lines[1] == f"run_id={run_id}"
    assert lines[2] == "candidate_id=local"
    assert lines[3] == f"run_dir={run_dir}"
    assert lines[4] == "status=success"
    assert lines[5] == "created_at=2026-02-14T16:55:01Z"
    assert lines[6] == "git_sha=abc123"
    assert lines[7] == f"run_summary={run_summary_path}"
    assert lines[8] == f"run_health={run_health_path}"
    assert lines[9].startswith("primary_artifact_1=")
    assert lines[10].startswith("primary_artifact_2=")
    assert lines[11].startswith("primary_artifact_3=")
    assert lines[12] == "RUN_SHOW_END"


def test_cli_runs_show_does_not_print_raw_candidate_text(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    run_id = "2026-02-14T16:55:01Z"
    run_dir = state_dir / "runs" / "20260214T165501Z"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_summary_path = run_dir / "run_summary.v1.json"
    run_summary_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "success",
                "resume_text": "SECRET_DO_NOT_PRINT",
                "primary_artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "RUN_METADATA_DIR", state_dir / "runs")
    monkeypatch.setattr(cli, "candidate_run_metadata_dir", lambda _: state_dir / "candidates" / "local" / "runs")
    monkeypatch.setattr(
        cli,
        "get_run_as_dict",
        lambda run_id, candidate_id: {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "status": "success",
            "created_at": "2026-02-14T16:55:01Z",
            "git_sha": "abc123",
            "summary_path": str(run_summary_path),
            "health_path": None,
        },
    )

    rc = cli.main(["runs", "show", run_id, "--candidate-id", "local"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "SECRET_DO_NOT_PRINT" not in out
    assert "RUN_SHOW_BEGIN" in out
    assert "RUN_SHOW_END" in out


def test_cli_runs_artifacts_prints_primary_table(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    run_id = "2026-02-14T16:55:01Z"
    run_dir = state_dir / "runs" / "20260214T165501Z"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_summary_path = run_dir / "run_summary.v1.json"
    run_summary_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "success",
                "primary_artifacts": [
                    {
                        "artifact_key": "shortlist_md",
                        "provider": "openai",
                        "profile": "cs",
                        "path": "state/runs/20260214T165501Z/openai/cs/openai_shortlist.cs.md",
                        "sha256": "zzz",
                        "bytes": 3,
                    },
                    {
                        "artifact_key": "ranked_json",
                        "provider": "openai",
                        "profile": "cs",
                        "path": "state/runs/20260214T165501Z/openai/cs/openai_ranked_jobs.cs.json",
                        "sha256": "aaa",
                        "bytes": 1,
                    },
                    {
                        "artifact_key": "ranked_csv",
                        "provider": "openai",
                        "profile": "cs",
                        "path": "state/runs/20260214T165501Z/openai/cs/openai_ranked_jobs.cs.csv",
                        "sha256": "bbb",
                        "bytes": 2,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "RUN_METADATA_DIR", state_dir / "runs")
    monkeypatch.setattr(cli, "candidate_run_metadata_dir", lambda _: state_dir / "candidates" / "local" / "runs")
    monkeypatch.setattr(
        cli,
        "get_run_as_dict",
        lambda run_id, candidate_id: {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "summary_path": str(run_summary_path),
            "health_path": None,
            "status": "success",
            "created_at": run_id,
            "git_sha": "abc123",
        },
    )

    rc = cli.main(["runs", "artifacts", run_id, "--candidate-id", "local"])
    assert rc == 0
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line]
    assert lines[0].startswith("ARTIFACT_KEY")
    assert lines[2].lstrip().startswith("ranked_json")
    assert lines[3].lstrip().startswith("ranked_csv")
    assert lines[4].lstrip().startswith("shortlist_md")
    assert lines[-1] == "ROWS=3"


def test_cli_runs_artifacts_requires_summary(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(cli, "RUN_METADATA_DIR", state_dir / "runs")
    monkeypatch.setattr(cli, "candidate_run_metadata_dir", lambda _: state_dir / "candidates" / "local" / "runs")
    monkeypatch.setattr(cli, "get_run_as_dict", lambda run_id, candidate_id: None)
    with pytest.raises(SystemExit, match="run_summary not found"):
        cli.main(["runs", "artifacts", "2026-02-14T16:55:01Z", "--candidate-id", "local"])
