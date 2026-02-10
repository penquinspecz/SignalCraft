#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_PROVIDERS = ["openai"]
DEFAULT_PROFILES = ["cs"]
BASE_REQUIRED = [
    "exit_code.txt",
    "metadata.json",
    "run_report.json",
    "smoke.log",
    "smoke_summary.json",
]


def _required_artifacts(providers: list[str], profiles: list[str]) -> list[str]:
    required = list(BASE_REQUIRED)
    for provider in sorted(providers):
        required.append(f"{provider}_labeled_jobs.json")
        for profile in sorted(profiles):
            required.append(f"{provider}_ranked_jobs.{profile}.csv")
            required.append(f"{provider}_ranked_jobs.{profile}.json")
    return sorted(required)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate CI smoke artifact layout offline.")
    parser.add_argument("artifacts_dir", help="Path to smoke artifacts directory")
    parser.add_argument("--providers", default=",".join(DEFAULT_PROVIDERS), help="Comma-separated providers")
    parser.add_argument("--profiles", default=",".join(DEFAULT_PROFILES), help="Comma-separated profiles")
    args = parser.parse_args(argv)

    artifacts_dir = Path(args.artifacts_dir)
    providers = [item.strip() for item in args.providers.split(",") if item.strip()]
    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    if not providers:
        raise RuntimeError("No providers specified")
    if not profiles:
        raise RuntimeError("No profiles specified")

    missing: list[str] = []
    empty: list[str] = []
    for rel_path in _required_artifacts(providers, profiles):
        path = artifacts_dir / rel_path
        if not path.exists():
            missing.append(rel_path)
            continue
        if path.stat().st_size == 0:
            empty.append(rel_path)

    if missing or empty:
        lines = [
            f"artifact_contract_check failed for {artifacts_dir}",
            f"required_providers={','.join(sorted(providers))}",
            f"required_profiles={','.join(sorted(profiles))}",
        ]
        if missing:
            lines.append("missing=" + ",".join(sorted(missing)))
        if empty:
            lines.append("empty=" + ",".join(sorted(empty)))
        raise RuntimeError("\n".join(lines))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1)
