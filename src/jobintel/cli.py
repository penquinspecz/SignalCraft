"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from ji_engine.config import DEFAULT_CANDIDATE_ID, RUN_METADATA_DIR, candidate_run_metadata_dir, sanitize_candidate_id
from ji_engine.providers.openai_provider import CAREERS_SEARCH_URL
from ji_engine.providers.registry import load_providers_config
from ji_engine.providers.selection import DEFAULTS_CONFIG_PATH, select_provider_ids
from ji_engine.run_id import sanitize_run_id
from ji_engine.state.run_index import get_run_as_dict, list_runs_as_dicts

from .safety.diff import build_safety_diff_report, load_jobs_from_path, render_summary, write_report
from .snapshots.refresh import refresh_snapshot
from .snapshots.validate import MIN_BYTES_DEFAULT, validate_snapshots

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROVIDERS_CONFIG = REPO_ROOT / "config" / "providers.json"


def _setup_logging() -> None:
    if logging.getLogger().hasHandlers():
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_provider_map(path: Path) -> Dict[str, dict]:
    providers = load_providers_config(path)
    return {p["provider_id"]: p for p in providers}


def _fallback_provider(provider_id: str) -> Optional[dict]:
    if provider_id != "openai":
        return None
    return {
        "provider_id": "openai",
        "careers_url": CAREERS_SEARCH_URL,
        "snapshot_path": str(REPO_ROOT / "data" / "openai_snapshots" / "index.html"),
    }


def _resolve_providers(provider_arg: str, providers_config: Path) -> List[dict]:
    provider_arg = provider_arg.lower().strip()
    provider_map = _load_provider_map(providers_config) if providers_config.exists() else {}

    if provider_arg == "all":
        return [provider_map[key] for key in sorted(provider_map.keys())]

    if provider_arg in provider_map:
        return [provider_map[provider_arg]]

    fallback = _fallback_provider(provider_arg)
    if fallback:
        return [fallback]

    raise SystemExit(f"Unknown provider '{provider_arg}'.")


def _refresh_snapshots(args: argparse.Namespace) -> int:
    _setup_logging()

    providers_config = Path(args.providers_config)
    if args.provider == "all" and args.out:
        raise SystemExit("--out cannot be used with --provider all")
    if not args.out:
        raise SystemExit("--out is required for snapshot writes; use an explicit output path.")

    targets = _resolve_providers(args.provider, providers_config)
    status = 0
    for provider in targets:
        provider_id = provider["provider_id"]
        url = provider.get("careers_url") or provider.get("board_url") or CAREERS_SEARCH_URL
        out_path = Path(args.out)
        fetch_method = (args.fetch or os.environ.get("JOBINTEL_SNAPSHOT_FETCH") or "requests").lower()
        extraction_mode = provider.get("extraction_mode") or provider.get("type")

        try:
            exit_code = refresh_snapshot(
                provider_id,
                url,
                out_path,
                force=args.force,
                timeout=args.timeout,
                min_bytes=args.min_bytes,
                fetch_method=fetch_method,
                headers={"User-Agent": args.user_agent},
                extraction_mode=extraction_mode,
            )
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        if exit_code != 0:
            status = exit_code
    return status


def _validate_snapshots(args: argparse.Namespace) -> int:
    providers_config = Path(args.providers_config)
    providers_cfg = load_providers_config(providers_config)
    if args.all:
        provider_ids: List[str] = []
    else:
        provider_arg = (args.provider or "").lower().strip()
        if provider_arg == "all":
            raise SystemExit("Use --all to validate discovered snapshots.")
        try:
            provider_ids = select_provider_ids(
                providers_arg=provider_arg,
                providers_config_path=providers_config,
                defaults_path=REPO_ROOT / DEFAULTS_CONFIG_PATH,
                env=os.environ,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    results = validate_snapshots(
        providers_cfg,
        provider_ids=provider_ids,
        validate_all=args.all,
        data_dir=Path(args.data_dir) if args.data_dir else None,
    )
    failures = [result for result in results if not result.ok]
    for result in results:
        if result.skipped:
            status = "SKIP"
        else:
            status = "OK" if result.ok else "FAIL"
        print(f"[snapshots] {status} {result.provider}: {result.path} ({result.reason})")

    if failures:
        print("Snapshot validation failed:")
        for result in failures:
            print(f"- {result.provider}: {result.path} ({result.reason})")
        return 1
    return 0


def _split_csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _merge_profiles(args: argparse.Namespace) -> list[str]:
    profiles = []
    profiles.extend(_split_csv(args.profiles))
    profiles.extend(_split_csv(args.role))
    seen = set()
    ordered = []
    for profile in profiles:
        if profile in seen:
            continue
        seen.add(profile)
        ordered.append(profile)
    return ordered


def _run_daily(args: argparse.Namespace) -> int:
    _setup_logging()

    profiles = _merge_profiles(args)
    if not profiles:
        raise SystemExit("No profiles provided. Use --role or --profiles.")
    safe_candidate_id = _validate_candidate_for_run(args.candidate_id)

    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_daily.py"),
        "--profiles",
        ",".join(profiles),
    ]
    if args.providers:
        cmd.extend(["--providers", args.providers])
    if args.offline:
        cmd.append("--offline")
    if args.no_post:
        cmd.append("--no_post")
    if args.no_enrich:
        cmd.append("--no_enrich")
    if args.ai:
        cmd.append("--ai")
    if args.ai_only:
        cmd.append("--ai_only")

    env = os.environ.copy()
    env["JOBINTEL_CANDIDATE_ID"] = safe_candidate_id
    if args.offline:
        env["CAREERS_MODE"] = "SNAPSHOT"

    logging.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, env=env, check=False, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    _print_run_receipt_if_available(safe_candidate_id, result.stdout or "")
    return result.returncode


def _run_summary_path(candidate_id: str, run_id: str) -> Path:
    run_root = RUN_METADATA_DIR if candidate_id == DEFAULT_CANDIDATE_ID else candidate_run_metadata_dir(candidate_id)
    return run_root / sanitize_run_id(run_id) / "run_summary.v1.json"


def _run_dir(candidate_id: str, run_id: str) -> Path:
    run_root = RUN_METADATA_DIR if candidate_id == DEFAULT_CANDIDATE_ID else candidate_run_metadata_dir(candidate_id)
    return run_root / sanitize_run_id(run_id)


def _run_health_path(candidate_id: str, run_id: str) -> Path:
    return _run_dir(candidate_id, run_id) / "run_health.v1.json"


def _read_json_dict(path: Path) -> Optional[Dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _absolute_path_text(path_value: str) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    return str((REPO_ROOT / candidate).resolve())


def _primary_artifact_paths(summary_payload: Optional[Dict[str, object]]) -> List[str]:
    if not summary_payload:
        return []
    artifacts = summary_payload.get("primary_artifacts")
    if not isinstance(artifacts, list):
        return []
    paths: List[str] = []
    for entry in artifacts:
        if not isinstance(entry, dict):
            continue
        raw_path = entry.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            paths.append(_absolute_path_text(raw_path))
        if len(paths) >= 3:
            break
    return paths


def _extract_run_id(stdout: str) -> Optional[str]:
    for line in stdout.splitlines():
        if line.startswith("JOBINTEL_RUN_ID="):
            run_id = line.split("=", 1)[1].strip()
            if run_id:
                return run_id
    return None


def _print_run_receipt_if_available(candidate_id: str, stdout: str) -> None:
    run_id = _extract_run_id(stdout)
    if not run_id:
        return
    run_dir = _run_dir(candidate_id, run_id)
    summary_path = _run_summary_path(candidate_id, run_id)
    health_path = _run_health_path(candidate_id, run_id)
    if not summary_path.exists() and not health_path.exists():
        return
    summary_payload = _read_json_dict(summary_path) if summary_path.exists() else None
    health_payload = _read_json_dict(health_path) if health_path.exists() else None
    status = None
    if isinstance(summary_payload, dict):
        value = summary_payload.get("status")
        if isinstance(value, str) and value.strip():
            status = value
    if status is None and isinstance(health_payload, dict):
        value = health_payload.get("status")
        if isinstance(value, str) and value.strip():
            status = value

    lines = [f"run_id={run_id}", f"run_dir={run_dir}"]
    if status is not None:
        lines.append(f"status={status}")
    if summary_path.exists():
        lines.append(f"run_summary={summary_path}")
    if health_path.exists():
        lines.append(f"run_health={health_path}")
    for idx, path in enumerate(_primary_artifact_paths(summary_payload), start=1):
        lines.append(f"primary_artifact_{idx}={path}")

    print("RUN_RECEIPT_BEGIN")
    for line in lines:
        print(line)
    print("RUN_RECEIPT_END")

    # Backward-compatibility for existing consumers.
    if summary_path.exists() and status in {"success", "partial"}:
        print(f"RUN_SUMMARY_PATH={summary_path}")


def _validate_candidate_for_run(candidate_id: str) -> str:
    safe_candidate_id = sanitize_candidate_id(candidate_id)
    from ji_engine.candidates import registry as candidate_registry

    registry = candidate_registry.load_registry()
    known_candidates = {entry.candidate_id for entry in registry.candidates}
    if safe_candidate_id not in known_candidates:
        raise SystemExit(
            f"candidate '{safe_candidate_id}' is not registered. "
            f"Run `python scripts/candidates.py bootstrap {safe_candidate_id}` first."
        )
    try:
        candidate_registry.load_candidate_profile(safe_candidate_id)
    except candidate_registry.CandidateValidationError as exc:
        raise SystemExit(
            f"candidate '{safe_candidate_id}' profile is invalid: {exc}. "
            f"Run `python scripts/candidates.py doctor {safe_candidate_id}`."
        ) from exc
    return safe_candidate_id


def _add_run_daily_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--role", help="Profile role name (e.g. cs).")
    parser.add_argument("--profiles", help="Comma-separated profiles (e.g. cs or cs,tam,se).")
    parser.add_argument("--providers", "--provider", dest="providers", help="Comma-separated provider ids.")
    parser.add_argument("--offline", action="store_true", help="Force snapshot mode (no live scraping).")
    parser.add_argument("--no_post", "--no-post", dest="no_post", action="store_true")
    parser.add_argument("--no_enrich", "--no-enrich", dest="no_enrich", action="store_true")
    parser.add_argument("--ai", action="store_true")
    parser.add_argument("--ai_only", action="store_true")
    parser.add_argument(
        "--candidate-id",
        "--candidate_id",
        dest="candidate_id",
        default=DEFAULT_CANDIDATE_ID,
        help=f"Candidate namespace id (default: {DEFAULT_CANDIDATE_ID}).",
    )


def _safety_diff(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline)
    candidate_path = Path(args.candidate)
    baseline_jobs = load_jobs_from_path(
        baseline_path,
        provider=args.provider,
        profile=args.profile,
    )
    candidate_jobs = load_jobs_from_path(
        candidate_path,
        provider=args.provider,
        profile=args.profile,
    )
    report = build_safety_diff_report(
        baseline_jobs,
        candidate_jobs,
        baseline_path=str(baseline_path),
        candidate_path=str(candidate_path),
        top_n=args.top,
    )
    report_path = Path(args.report_out)
    write_report(report, report_path)
    print(render_summary(report))
    print(f"Report written to {report_path}")
    return 0


def _runs_list(args: argparse.Namespace) -> int:
    candidate_id = sanitize_candidate_id(args.candidate_id)
    rows = list_runs_as_dicts(candidate_id=candidate_id, limit=args.limit)
    headers = ("RUN_ID", "CANDIDATE", "STATUS", "CREATED_AT", "SUMMARY_PATH", "HEALTH_PATH", "GIT_SHA")

    table_rows: List[List[str]] = []
    for row in rows:
        table_rows.append(
            [
                str(row.get("run_id") or ""),
                str(row.get("candidate_id") or DEFAULT_CANDIDATE_ID),
                str(row.get("status") or ""),
                str(row.get("created_at") or ""),
                str(row.get("summary_path") or ""),
                str(row.get("health_path") or ""),
                str(row.get("git_sha") or ""),
            ]
        )

    widths = [len(h) for h in headers]
    for row in table_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    fmt = "  ".join("{:<" + str(width) + "}" for width in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * len(h) for h in headers)))
    for row in table_rows:
        print(fmt.format(*row))
    print(f"ROWS={len(table_rows)}")
    return 0


def _resolve_summary_health_paths(
    candidate_id: str,
    run_id: str,
    run_row: Optional[Dict[str, object]],
) -> tuple[Path, Path]:
    default_summary = _run_summary_path(candidate_id, run_id)
    default_health = _run_health_path(candidate_id, run_id)
    if not run_row:
        return default_summary, default_health

    summary_raw = run_row.get("summary_path")
    health_raw = run_row.get("health_path")

    summary_path = Path(summary_raw) if isinstance(summary_raw, str) and summary_raw.strip() else default_summary
    health_path = Path(health_raw) if isinstance(health_raw, str) and health_raw.strip() else default_health
    return summary_path, health_path


def _extract_status(
    summary_payload: Optional[Dict[str, object]],
    health_payload: Optional[Dict[str, object]],
    run_row: Optional[Dict[str, object]],
) -> Optional[str]:
    if isinstance(summary_payload, dict):
        value = summary_payload.get("status")
        if isinstance(value, str) and value.strip():
            return value
    if isinstance(health_payload, dict):
        value = health_payload.get("status")
        if isinstance(value, str) and value.strip():
            return value
    if isinstance(run_row, dict):
        value = run_row.get("status")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_created_at(
    summary_payload: Optional[Dict[str, object]],
    run_row: Optional[Dict[str, object]],
) -> Optional[str]:
    if isinstance(summary_payload, dict):
        value = summary_payload.get("created_at_utc")
        if isinstance(value, str) and value.strip():
            return value
    if isinstance(run_row, dict):
        value = run_row.get("created_at")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_git_sha(
    summary_payload: Optional[Dict[str, object]],
    run_row: Optional[Dict[str, object]],
) -> Optional[str]:
    if isinstance(summary_payload, dict):
        value = summary_payload.get("git_sha")
        if isinstance(value, str) and value.strip():
            return value
    if isinstance(run_row, dict):
        value = run_row.get("git_sha")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _runs_show(args: argparse.Namespace) -> int:
    candidate_id = sanitize_candidate_id(args.candidate_id)
    run_id = args.run_id.strip()
    run_row = get_run_as_dict(run_id=run_id, candidate_id=candidate_id)
    summary_path, health_path = _resolve_summary_health_paths(candidate_id, run_id, run_row)
    summary_payload = _read_json_dict(summary_path) if summary_path.exists() else None
    health_payload = _read_json_dict(health_path) if health_path.exists() else None

    if run_row is None and summary_payload is None and health_payload is None:
        raise SystemExit(
            f"run '{run_id}' not found for candidate '{candidate_id}'. "
            f"Use `python -m jobintel.cli runs list --candidate-id {candidate_id}`."
        )

    status = _extract_status(summary_payload, health_payload, run_row)
    created_at = _extract_created_at(summary_payload, run_row)
    git_sha = _extract_git_sha(summary_payload, run_row)
    run_dir = _run_dir(candidate_id, run_id)

    lines = [
        f"run_id={run_id}",
        f"candidate_id={candidate_id}",
        f"run_dir={run_dir}",
    ]
    if status is not None:
        lines.append(f"status={status}")
    if created_at is not None:
        lines.append(f"created_at={created_at}")
    if git_sha is not None:
        lines.append(f"git_sha={git_sha}")
    if summary_path.exists() or (run_row and run_row.get("summary_path")):
        lines.append(f"run_summary={summary_path}")
    if health_path.exists() or (run_row and run_row.get("health_path")):
        lines.append(f"run_health={health_path}")
    for idx, path in enumerate(_primary_artifact_paths(summary_payload), start=1):
        lines.append(f"primary_artifact_{idx}={path}")

    print("RUN_SHOW_BEGIN")
    for line in lines:
        print(line)
    print("RUN_SHOW_END")
    return 0


def _artifact_key_rank(artifact_key: str) -> int:
    ranks = {"ranked_json": 0, "ranked_csv": 1, "shortlist_md": 2}
    return ranks.get(artifact_key, 99)


def _primary_artifacts_rows(summary_payload: Optional[Dict[str, object]]) -> List[List[str]]:
    if not summary_payload:
        return []
    raw_items = summary_payload.get("primary_artifacts")
    if not isinstance(raw_items, list):
        return []

    normalized: List[Dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        artifact_key = item.get("artifact_key")
        provider = item.get("provider")
        profile = item.get("profile")
        path = item.get("path")
        sha256 = item.get("sha256")
        bytes_value = item.get("bytes")
        if not all(isinstance(value, str) and value.strip() for value in (artifact_key, provider, profile, path)):
            continue
        normalized.append(
            {
                "artifact_key": artifact_key,
                "provider": provider,
                "profile": profile,
                "path": path,
                "sha256": sha256 if isinstance(sha256, str) else "",
                "bytes": str(bytes_value) if isinstance(bytes_value, int) else "",
            }
        )

    normalized.sort(
        key=lambda item: (
            _artifact_key_rank(item["artifact_key"]),
            item["provider"],
            item["profile"],
            item["path"],
        )
    )
    return [
        [
            item["artifact_key"],
            item["provider"],
            item["profile"],
            item["path"],
            item["sha256"],
            item["bytes"],
        ]
        for item in normalized
    ]


def _runs_artifacts(args: argparse.Namespace) -> int:
    candidate_id = sanitize_candidate_id(args.candidate_id)
    run_id = args.run_id.strip()
    run_row = get_run_as_dict(run_id=run_id, candidate_id=candidate_id)
    summary_path, _ = _resolve_summary_health_paths(candidate_id, run_id, run_row)

    if not summary_path.exists():
        raise SystemExit(
            f"run_summary not found for run '{run_id}' candidate '{candidate_id}' at {summary_path}. "
            "Run the pipeline first or rebuild run index metadata."
        )
    summary_payload = _read_json_dict(summary_path)
    if summary_payload is None:
        raise SystemExit(f"run_summary at {summary_path} is not valid JSON object")

    headers = ("ARTIFACT_KEY", "PROVIDER", "PROFILE", "PATH", "SHA256", "BYTES")
    table_rows = _primary_artifacts_rows(summary_payload)
    widths = [len(h) for h in headers]
    for row in table_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    fmt = "  ".join("{:<" + str(width) + "}" for width in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * len(h) for h in headers)))
    for row in table_rows:
        print(fmt.format(*row))
    print(f"ROWS={len(table_rows)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobintel",
        description="SignalCraft CLI (Job Intelligence Engine, JIE).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshots = subparsers.add_parser("snapshots", help="Snapshot maintenance")
    snapshots_sub = snapshots.add_subparsers(dest="snapshots_command", required=True)

    refresh = snapshots_sub.add_parser("refresh", help="Refresh provider snapshots")
    refresh.add_argument("--provider", required=True, help="Provider id or 'all'.")
    refresh.add_argument("--out", help="Output snapshot path (required).")
    refresh.add_argument("--force", action="store_true", help="Write snapshot even if validation fails.")
    refresh.add_argument("--fetch", choices=["requests", "playwright"], default="requests")
    refresh.add_argument("--timeout", type=float, default=20.0)
    refresh.add_argument("--min-bytes", type=int, default=MIN_BYTES_DEFAULT)
    refresh.add_argument("--user-agent", default="signalcraft/0.1 (+snapshot-refresh)")
    refresh.add_argument(
        "--providers-config",
        default=str(DEFAULT_PROVIDERS_CONFIG),
        help="Path to providers config JSON.",
    )
    refresh.set_defaults(func=_refresh_snapshots)

    validate_cmd = snapshots_sub.add_parser("validate", help="Validate provider snapshots")
    validate_cmd.add_argument(
        "--provider",
        help=(
            "Provider id(s) to validate. If omitted, selection precedence is "
            "--provider, JOBINTEL_PROVIDER_ID, config/defaults.json, then first enabled provider."
        ),
    )
    validate_cmd.add_argument("--all", action="store_true", help="Validate all known providers.")
    validate_cmd.add_argument("--data-dir", help="Base data directory (default: JOBINTEL_DATA_DIR or data).")
    validate_cmd.add_argument(
        "--providers-config",
        default=str(DEFAULT_PROVIDERS_CONFIG),
        help="Path to providers config JSON.",
    )
    validate_cmd.set_defaults(func=_validate_snapshots)

    run_cmd = subparsers.add_parser("run", help="Run pipeline helpers")
    _add_run_daily_args(run_cmd)
    run_cmd.set_defaults(func=_run_daily)
    run_sub = run_cmd.add_subparsers(dest="run_command")
    run_daily_cmd = run_sub.add_parser("daily", help="Run daily pipeline with candidate safety checks")
    _add_run_daily_args(run_daily_cmd)
    run_daily_cmd.set_defaults(func=_run_daily)

    runs_cmd = subparsers.add_parser("runs", help="Run index helpers")
    runs_sub = runs_cmd.add_subparsers(dest="runs_command", required=True)
    runs_list_cmd = runs_sub.add_parser("list", help="List recent runs from local sqlite index")
    runs_list_cmd.add_argument(
        "--candidate-id",
        "--candidate_id",
        dest="candidate_id",
        default=DEFAULT_CANDIDATE_ID,
        help=f"Candidate namespace id (default: {DEFAULT_CANDIDATE_ID}).",
    )
    runs_list_cmd.add_argument("--limit", type=int, default=20, help="Maximum rows to print (default: 20).")
    runs_list_cmd.set_defaults(func=_runs_list)
    runs_show_cmd = runs_sub.add_parser("show", help="Show canonical pointers for one run id")
    runs_show_cmd.add_argument("run_id", help="Run id (e.g. 2026-02-14T16:55:01Z).")
    runs_show_cmd.add_argument(
        "--candidate-id",
        "--candidate_id",
        dest="candidate_id",
        default=DEFAULT_CANDIDATE_ID,
        help=f"Candidate namespace id (default: {DEFAULT_CANDIDATE_ID}).",
    )
    runs_show_cmd.set_defaults(func=_runs_show)
    runs_artifacts_cmd = runs_sub.add_parser(
        "artifacts",
        help="List primary run artifacts (ranked_json/ranked_csv/shortlist_md) for one run id",
    )
    runs_artifacts_cmd.add_argument("run_id", help="Run id (e.g. 2026-02-14T16:55:01Z).")
    runs_artifacts_cmd.add_argument(
        "--candidate-id",
        "--candidate_id",
        dest="candidate_id",
        default=DEFAULT_CANDIDATE_ID,
        help=f"Candidate namespace id (default: {DEFAULT_CANDIDATE_ID}).",
    )
    runs_artifacts_cmd.set_defaults(func=_runs_artifacts)

    safety_cmd = subparsers.add_parser("safety", help="Semantic safety net tooling")
    safety_sub = safety_cmd.add_subparsers(dest="safety_command", required=True)

    diff_cmd = safety_sub.add_parser("diff", help="Compare baseline vs candidate job outputs")
    diff_cmd.add_argument("--baseline", required=True, help="Baseline run or jobs JSON path.")
    diff_cmd.add_argument("--candidate", required=True, help="Candidate run or jobs JSON path.")
    diff_cmd.add_argument("--provider", help="Provider id when using run reports with multiple providers.")
    diff_cmd.add_argument("--profile", help="Profile name when using run reports with multiple profiles.")
    diff_cmd.add_argument("--top", type=int, default=5, help="Top N changed records to include.")
    diff_cmd.add_argument(
        "--report-out",
        default="safety_diff_report.json",
        help="Output path for JSON report.",
    )
    diff_cmd.set_defaults(func=_safety_diff)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
