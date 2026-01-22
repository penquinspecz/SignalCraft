import hashlib
import json
import subprocess
import sys
from pathlib import Path

import scripts.replay_run as replay_run


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jobs(path: Path) -> None:
    jobs = [
        {
            "job_id": "1",
            "title": "Role A",
            "score": 10,
            "apply_url": "http://example.com/a",
            "enrich_status": "enriched",
        },
        {
            "job_id": "2",
            "title": "Role B",
            "score": 20,
            "apply_url": "http://example.com/b",
            "enrich_status": "enriched",
        },
    ]
    path.write_text(json.dumps(jobs), encoding="utf-8")


def test_replay_run_reproducible(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    _write_jobs(input_path)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    cmd = [
        sys.executable,
        "scripts/score_jobs.py",
        "--profile",
        "cs",
        "--in_path",
        str(input_path),
        "--out_json",
        str(out_dir / "ranked_jobs.cs.json"),
        "--out_csv",
        str(out_dir / "ranked_jobs.cs.csv"),
        "--out_families",
        str(out_dir / "ranked_families.cs.json"),
        "--out_md",
        str(out_dir / "shortlist.cs.md"),
        "--out_md_top_n",
        str(out_dir / "top.cs.md"),
        "--min_score",
        "40",
    ]
    subprocess.run(cmd, check=True)

    report = {
        "run_id": "2026-01-22T00:00:00Z",
        "flags": {"min_score": 40},
        "inputs": {
            "raw_jobs_json": {"path": str(input_path), "sha256": _sha256(input_path)},
        },
        "scoring_inputs_by_profile": {
            "cs": {"path": str(input_path), "sha256": _sha256(input_path)},
        },
        "outputs_by_profile": {
            "cs": {
                "ranked_json": {"path": str(out_dir / "ranked_jobs.cs.json"), "sha256": _sha256(out_dir / "ranked_jobs.cs.json")},
                "ranked_csv": {"path": str(out_dir / "ranked_jobs.cs.csv"), "sha256": _sha256(out_dir / "ranked_jobs.cs.csv")},
                "ranked_families_json": {"path": str(out_dir / "ranked_families.cs.json"), "sha256": _sha256(out_dir / "ranked_families.cs.json")},
                "shortlist_md": {"path": str(out_dir / "shortlist.cs.md"), "sha256": _sha256(out_dir / "shortlist.cs.md")},
                "top_md": {"path": str(out_dir / "top.cs.md"), "sha256": _sha256(out_dir / "top.cs.md")},
            }
        },
    }
    report_path = tmp_path / "run.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    rc = replay_run.main(["--run-report", str(report_path), "--profile", "cs", "--out-dir", str(tmp_path / "replay")])
    assert rc == 0


def test_replay_run_hash_mismatch_returns_2(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    _write_jobs(input_path)

    report = {
        "run_id": "2026-01-22T00:00:00Z",
        "flags": {"min_score": 40},
        "inputs": {
            "raw_jobs_json": {"path": str(input_path), "sha256": "bad"},
        },
        "scoring_inputs_by_profile": {
            "cs": {"path": str(input_path), "sha256": _sha256(input_path)},
        },
        "outputs_by_profile": {
            "cs": {
                "ranked_json": {"path": str(tmp_path / "missing.json"), "sha256": "bad"},
            }
        },
    }
    report_path = tmp_path / "run.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    rc = replay_run.main(["--run-report", str(report_path), "--profile", "cs", "--out-dir", str(tmp_path / "replay")])
    assert rc == 2
