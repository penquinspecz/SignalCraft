#!/usr/bin/env python3
"""Inspect labeled jobs output for quick sanity checks."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin


def _load_jobs(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: labeled jobs file not found: {path}", file=sys.stderr)
        raise
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise
    if not isinstance(data, list):
        raise ValueError(f"expected a list of jobs in {path}")
    return [job for job in data if isinstance(job, dict)]


def _counts_by_relevance(jobs: Iterable[Dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for job in jobs:
        relevance = str(job.get("relevance", "UNKNOWN"))
        counter[relevance] += 1
    return counter


def _resolve_detail_url(detail_url: Optional[str], base_url: str) -> Optional[str]:
    if not detail_url:
        return None
    if detail_url.startswith("http://") or detail_url.startswith("https://"):
        return detail_url
    if detail_url.startswith("/"):
        return urljoin(base_url, detail_url)
    return detail_url


def _print_section(title: str, jobs: List[Dict[str, Any]], limit: int, base_url: str) -> None:
    print(f"\n{title} (showing up to {limit})")
    if not jobs:
        print("  (none)")
        return
    for job in jobs[:limit]:
        job_title = job.get("title", "(missing title)")
        relevance = job.get("relevance", "UNKNOWN")
        apply_url = job.get("apply_url")
        detail_url = _resolve_detail_url(job.get("detail_url"), base_url)
        print(f"- {job_title}")
        print(f"  relevance: {relevance}")
        print(f"  apply_url: {apply_url}")
        print(f"  detail_url: {detail_url}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect labeled jobs JSON.")
    parser.add_argument(
        "--in_path",
        default="data/openai_labeled_jobs.json",
        help="Path to labeled jobs JSON.",
    )
    parser.add_argument("--n", type=int, default=5, help="Number of jobs to show per section.")
    parser.add_argument(
        "--base_url",
        default="https://openai.com",
        help="Base URL for resolving detail_url when it is relative.",
    )
    args = parser.parse_args(argv)

    path = Path(args.in_path)
    try:
        jobs = _load_jobs(path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 1

    counts = _counts_by_relevance(jobs)
    total = sum(counts.values())
    print(f"Labeled jobs: {total}")
    for key in sorted(counts.keys()):
        print(f"  {key}: {counts[key]}")

    relevant = [job for job in jobs if str(job.get("relevance")) == "RELEVANT"]
    maybe = [job for job in jobs if str(job.get("relevance")) == "MAYBE"]

    _print_section("RELEVANT", relevant, args.n, args.base_url)
    _print_section("MAYBE", maybe, args.n, args.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
