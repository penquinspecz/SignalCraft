#!/usr/bin/env python3
from __future__ import annotations

try:
    import _bootstrap  # type: ignore
except ModuleNotFoundError:
    from scripts import _bootstrap  # noqa: F401

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ji_engine.config import RUN_METADATA_DIR


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sanitize_run_id(run_id: str) -> str:
    return run_id.replace(":", "").replace("-", "").replace(".", "")


def _load_run_report(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_entry(
    label: str, path_str: Optional[str], expected_hash: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    if not path_str or not expected_hash:
        return f"{label}: missing path/hash", None
    path = Path(path_str)
    if not path.exists():
        return f"{label}: missing file {path}", None
    actual = _sha256(path)
    if actual != expected_hash:
        return None, f"{label}: sha256 mismatch (expected={expected_hash} actual={actual})"
    return None, None


def _collect_entries(report: Dict[str, Any], profile: str) -> List[Tuple[str, Optional[str], Optional[str]]]:
    entries: List[Tuple[str, Optional[str], Optional[str]]] = []

    inputs = report.get("inputs") or {}
    if isinstance(inputs, dict):
        for key, value in inputs.items():
            if isinstance(value, dict):
                entries.append((f"input:{key}", value.get("path"), value.get("sha256")))

    scoring_inputs = report.get("scoring_inputs_by_profile") or {}
    if isinstance(scoring_inputs, dict):
        value = scoring_inputs.get(profile)
        if isinstance(value, dict):
            entries.append((f"scoring_input:{profile}", value.get("path"), value.get("sha256")))

    return entries


def _collect_expected_outputs(report: Dict[str, Any], profile: str) -> Dict[str, Dict[str, Optional[str]]]:
    outputs = report.get("outputs_by_profile") or {}
    if not isinstance(outputs, dict):
        return {}
    value = outputs.get(profile)
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if isinstance(v, dict)}


def _resolve_report_path(run_id: Optional[str], run_report: Optional[str], runs_dir: Path) -> Path:
    if run_report:
        return Path(run_report)
    if not run_id:
        raise SystemExit("ERROR: provide --run-report or --run-id")
    sanitized = _sanitize_run_id(run_id)
    candidate = runs_dir / f"{sanitized}.json"
    if candidate.exists():
        return candidate
    nested = runs_dir / sanitized / "run_report.json"
    if nested.exists():
        return nested
    raise SystemExit(f"ERROR: run report not found at {candidate} or {nested}")


def _run_score_jobs(
    in_path: Path,
    out_dir: Path,
    profile: str,
    min_score: int,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"ranked_jobs.{profile}.json"
    out_csv = out_dir / f"ranked_jobs.{profile}.csv"
    out_families = out_dir / f"ranked_families.{profile}.json"
    out_md = out_dir / f"shortlist.{profile}.md"
    out_top = out_dir / f"top.{profile}.md"

    cmd = [
        sys.executable,
        "scripts/score_jobs.py",
        "--profile",
        profile,
        "--in_path",
        str(in_path),
        "--out_json",
        str(out_json),
        "--out_csv",
        str(out_csv),
        "--out_families",
        str(out_families),
        "--out_md",
        str(out_md),
        "--out_md_top_n",
        str(out_top),
        "--min_score",
        str(min_score),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Replay deterministic scoring from a run report.")
    parser.add_argument("--run-report", type=str, help="Path to run report JSON.")
    parser.add_argument("--run-id", type=str, help="Run id to locate under state/runs.")
    parser.add_argument("--runs-dir", type=str, help="Base runs dir (default: state/runs).")
    parser.add_argument("--out-dir", type=str, help="Output dir for replay artifacts.")
    parser.add_argument("--profile", type=str, default="cs", help="Profile to replay (default: cs).")
    args = parser.parse_args(argv)

    runs_dir = Path(args.runs_dir) if args.runs_dir else RUN_METADATA_DIR
    try:
        report_path = _resolve_report_path(args.run_id, args.run_report, runs_dir)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not report_path.exists():
        print(f"ERROR: run report not found at {report_path}", file=sys.stderr)
        return 2

    try:
        report = _load_run_report(report_path)
    except Exception as exc:
        print(f"ERROR: failed to load run report: {exc!r}", file=sys.stderr)
        return 3

    entries = _collect_entries(report, args.profile)
    if not entries:
        print("ERROR: run report missing inputs for profile", file=sys.stderr)
        return 2

    validation_errors: List[str] = []
    mismatches: List[str] = []
    for label, path_str, expected_hash in entries:
        val_err, mismatch = _validate_entry(label, path_str, expected_hash)
        if val_err:
            validation_errors.append(val_err)
        if mismatch:
            mismatches.append(mismatch)

    if validation_errors:
        print("NOT REPRODUCIBLE: missing files or invalid report entries")
        for err in validation_errors:
            print(f"- {err}")
        if mismatches:
            for err in mismatches:
                print(f"- {err}")
        return 2

    if mismatches:
        print("NOT REPRODUCIBLE: hash mismatches detected")
        for err in mismatches:
            print(f"- {err}")
        return 2

    scoring_inputs = report.get("scoring_inputs_by_profile") or {}
    scoring_entry = scoring_inputs.get(args.profile, {}) if isinstance(scoring_inputs, dict) else {}
    in_path_str = scoring_entry.get("path")
    if not in_path_str:
        print("NOT REPRODUCIBLE: missing scoring input path", file=sys.stderr)
        return 2

    in_path = Path(in_path_str)
    min_score = (report.get("flags") or {}).get("min_score", 40)
    out_dir = Path(args.out_dir) if args.out_dir else (runs_dir / _sanitize_run_id(report.get("run_id", "run")) / "replay")

    rc = _run_score_jobs(in_path, out_dir, args.profile, int(min_score))
    if rc != 0:
        print("ERROR: replay scoring failed", file=sys.stderr)
        return max(3, rc)

    expected_outputs = _collect_expected_outputs(report, args.profile)
    if not expected_outputs:
        print("NOT REPRODUCIBLE: run report missing output metadata", file=sys.stderr)
        return 2

    output_map = {
        "ranked_json": out_dir / f"ranked_jobs.{args.profile}.json",
        "ranked_csv": out_dir / f"ranked_jobs.{args.profile}.csv",
        "ranked_families_json": out_dir / f"ranked_families.{args.profile}.json",
        "shortlist_md": out_dir / f"shortlist.{args.profile}.md",
        "top_md": out_dir / f"top.{args.profile}.md",
    }

    mismatched_outputs: List[str] = []
    missing_outputs: List[str] = []
    for key, meta in expected_outputs.items():
        expected_hash = meta.get("sha256")
        out_path = output_map.get(key)
        if not out_path or not out_path.exists():
            missing_outputs.append(f"{key}: missing replay output")
            continue
        actual = _sha256(out_path)
        if expected_hash and actual != expected_hash:
            mismatched_outputs.append(f"{key}: sha256 mismatch (expected={expected_hash} actual={actual})")

    if missing_outputs or mismatched_outputs:
        print("NOT REPRODUCIBLE: output mismatch")
        for err in missing_outputs + mismatched_outputs:
            print(f"- {err}")
        return 2

    print("REPRODUCIBLE: outputs match run report hashes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
