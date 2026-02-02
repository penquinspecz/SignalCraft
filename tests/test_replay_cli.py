from __future__ import annotations

import json
from pathlib import Path

import scripts.replay_run as replay_run


def _write_bytes(path: Path, data: bytes) -> str:
    import hashlib

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _build_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ranked = run_dir / "openai_ranked_jobs.cs.json"
    sha = _write_bytes(ranked, b"[1]")
    report = {
        "run_id": "cli-test",
        "verifiable_artifacts": {
            "openai:cs:ranked_json": {
                "path": "openai/cs/openai_ranked_jobs.cs.json",
                "sha256": sha,
                "hash_algo": "sha256",
            }
        },
    }
    report_path = run_dir / "run_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    artifact_path = run_dir / "openai" / "cs" / "openai_ranked_jobs.cs.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(ranked.read_bytes())
    return run_dir


def test_replay_cli_json_ok(tmp_path: Path, capsys) -> None:
    run_dir = _build_run_dir(tmp_path)
    exit_code = replay_run.main(["--run-dir", str(run_dir), "--json"])
    out = capsys.readouterr().out
    assert '"elapsed_ms"' in out
    assert out.index('"elapsed_ms"') < out.index('"mismatches"') < out.index('"ok"') < out.index('"run_id"') < out.index('"verified"')
    payload = json.loads(out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["run_id"] == "cli-test"
    assert payload["mismatches"] == []


def test_replay_cli_json_mismatch(tmp_path: Path, capsys) -> None:
    run_dir = _build_run_dir(tmp_path)
    corrupt = run_dir / "openai" / "cs" / "openai_ranked_jobs.cs.json"
    corrupt.write_bytes(b"[2]")
    exit_code = replay_run.main(["--run-dir", str(run_dir), "--json", "--strict"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert exit_code == 2
    assert payload["ok"] is False
    assert payload["mismatches"]
    mismatch = payload["mismatches"][0]
    assert mismatch["expected"]
    assert mismatch["actual"]
    assert mismatch["path"].endswith("openai/cs/openai_ranked_jobs.cs.json")
