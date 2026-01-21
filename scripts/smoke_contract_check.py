#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, List


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to read {path}: {exc}") from exc


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows:
        return 0
    return max(len(rows) - 1, 0)


def _require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing required file: {path}")
    if path.stat().st_size == 0:
        raise RuntimeError(f"Empty required file: {path}")


def _validate_run_report(report: dict, labeled_count: int) -> None:
    providers = report.get("providers") or []
    if "openai" not in providers:
        raise RuntimeError("run_report.json missing provider=openai")

    selection = report.get("selection") or {}
    provenance = selection.get("scrape_provenance") or report.get("provenance_by_provider") or {}
    openai_meta = provenance.get("openai") or {}
    scrape_mode = (openai_meta.get("scrape_mode") or "").lower()
    if scrape_mode != "snapshot":
        raise RuntimeError(f"run_report.json scrape_mode expected SNAPSHOT, got {scrape_mode or 'missing'}")

    classified_count = selection.get("classified_job_count")
    if classified_count is None:
        by_provider = selection.get("classified_job_count_by_provider") or {}
        if "openai" in by_provider:
            classified_count = by_provider["openai"]
    if classified_count is None:
        tried = ["selection.classified_job_count", "selection.classified_job_count_by_provider.openai"]
        keys = sorted(report.keys())
        raise RuntimeError(
            "run_report.json missing classified_job_count "
            f"(tried {', '.join(tried)}; top-level keys: {', '.join(keys)})"
        )
    if int(classified_count) != labeled_count:
        raise RuntimeError(
            f"classified_job_count mismatch: report={classified_count} labeled_jobs={labeled_count}"
        )


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate deterministic smoke artifacts.")
    ap.add_argument("artifacts_dir", help="Path to smoke_artifacts directory.")
    ap.add_argument("--min-ranked", type=int, default=5, help="Minimum ranked jobs required.")
    args = ap.parse_args(argv)

    artifacts = Path(args.artifacts_dir)
    labeled_path = artifacts / "openai_labeled_jobs.json"
    ranked_json_path = artifacts / "openai_ranked_jobs.cs.json"
    ranked_csv_path = artifacts / "openai_ranked_jobs.cs.csv"
    run_report_path = artifacts / "run_report.json"

    _require_file(labeled_path)
    _require_file(ranked_json_path)
    _require_file(ranked_csv_path)
    _require_file(run_report_path)

    labeled_jobs = _load_json(labeled_path)
    if not isinstance(labeled_jobs, list) or not labeled_jobs:
        raise RuntimeError("openai_labeled_jobs.json must be a non-empty list")

    ranked_jobs = _load_json(ranked_json_path)
    if not isinstance(ranked_jobs, list):
        raise RuntimeError("openai_ranked_jobs.cs.json must be a list")
    if len(ranked_jobs) < args.min_ranked:
        raise RuntimeError(
            f"openai_ranked_jobs.cs.json has {len(ranked_jobs)} items (min {args.min_ranked})"
        )

    csv_rows = _count_csv_rows(ranked_csv_path)
    if csv_rows != len(ranked_jobs):
        raise RuntimeError(
            f"openai_ranked_jobs.cs.csv rows {csv_rows} != ranked JSON length {len(ranked_jobs)}"
        )

    run_report = _load_json(run_report_path)
    if not isinstance(run_report, dict):
        raise RuntimeError("run_report.json must be an object")
    _validate_run_report(run_report, len(labeled_jobs))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"smoke_contract_check: {exc}")
        raise SystemExit(1)
