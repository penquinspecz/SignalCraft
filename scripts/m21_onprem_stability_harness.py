#!/usr/bin/env python3
"""
M21 on-prem 72h stability harness.

Runs deterministic pipeline intervals, captures per-interval receipts,
and emits final replay/snapshot/determinism checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ji_engine.pipeline.run_pathing import sanitize_run_id

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "defaults.json"
DEFAULT_K8S_NAMESPACE = "jobintel"


@dataclass(frozen=True)
class CommandResult:
    argv: List[str]
    returncode: int
    stdout: str
    stderr: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


_sanitize_run_id = sanitize_run_id


def _default_run_id() -> str:
    stamp = _utc_now_iso().replace(":", "").replace("-", "")
    return stamp.replace(".", "")


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _maybe_load_defaults(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise SystemExit(f"config must be a JSON object: {path}")
    return payload


def _resolve_candidate(candidate_id: str, defaults: Dict[str, Any]) -> str:
    resolved = candidate_id or str(defaults.get("candidate_id") or "local")
    if not re.fullmatch(r"[a-z0-9_]{1,64}", resolved):
        raise SystemExit(f"invalid candidate_id {resolved!r}; must match [a-z0-9_]{{1,64}}")
    return resolved


def _run_command(argv: Sequence[str], *, env: Optional[Dict[str, str]] = None) -> CommandResult:
    proc = subprocess.run(list(argv), capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), check=False)
    return CommandResult(argv=list(argv), returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def _write_command_log(path: Path, result: CommandResult) -> None:
    lines = [
        "command: " + " ".join(result.argv),
        f"returncode: {result.returncode}",
        "--- stdout ---",
        result.stdout.rstrip(),
        "--- stderr ---",
        result.stderr.rstrip(),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _resolve_state_dir(explicit_state_dir: Optional[Path]) -> Path:
    if explicit_state_dir:
        return explicit_state_dir.resolve()
    return Path(os.environ.get("JOBINTEL_STATE_DIR", "state")).resolve()


def _resolve_data_dir(explicit_data_dir: Optional[Path]) -> Path:
    if explicit_data_dir:
        return explicit_data_dir.resolve()
    return Path(os.environ.get("JOBINTEL_DATA_DIR", "data")).resolve()


def _candidate_runs_dir(state_dir: Path, candidate_id: str) -> Path:
    return state_dir / "candidates" / candidate_id / "runs"


def _discover_latest_run_dir(state_dir: Path, candidate_id: str) -> Optional[Path]:
    root = _candidate_runs_dir(state_dir, candidate_id)
    if not root.exists():
        return None
    candidates: List[Path] = []
    for child in root.iterdir():
        if child.is_dir() and (child / "run_summary.v1.json").exists():
            candidates.append(child)
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p.stat().st_mtime, p.name))
    return candidates[-1]


def _artifact_hash_summary(run_dir: Path, profile: str) -> Dict[str, Dict[str, Any]]:
    files = {
        "run_summary": run_dir / "run_summary.v1.json",
        "run_health": run_dir / "run_health.v1.json",
        "provider_availability": run_dir / "artifacts" / "provider_availability_v1.json",
        "run_report": run_dir / "run_report.json",
        "explanation": run_dir / "artifacts" / "explanation_v1.json",
        "ai_insights": run_dir / "artifacts" / f"ai_insights.{profile}.json",
        "ai_job_briefs": run_dir / "artifacts" / f"ai_job_briefs.{profile}.json",
        "ai_job_briefs_error": run_dir / "artifacts" / f"ai_job_briefs.{profile}.error.json",
    }
    out: Dict[str, Dict[str, Any]] = {}
    for key, path in files.items():
        if path.exists():
            out[key] = {
                "path": _display_path(path),
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size,
            }
        else:
            out[key] = {"path": _display_path(path), "missing": True}
    return out


def _capture_k8s_snapshot(namespace: str, kube_context: str, checkpoint_dir: Path, skip_k8s: bool) -> Dict[str, Any]:
    if skip_k8s:
        return {"status": "skipped", "reason": "--skip-k8s"}
    if shutil.which("kubectl") is None:
        return {"status": "unavailable", "reason": "kubectl not found"}

    base = ["kubectl"]
    if kube_context:
        base.extend(["--context", kube_context])

    out: Dict[str, Any] = {"status": "ok", "commands": []}
    commands = [
        ("pods_json", base + ["-n", namespace, "get", "pods", "-o", "json"]),
        ("jobs_json", base + ["-n", namespace, "get", "jobs", "-o", "json"]),
        ("top_nodes", base + ["top", "nodes"]),
        ("top_pods", base + ["-n", namespace, "top", "pods"]),
    ]
    for label, argv in commands:
        result = _run_command(argv)
        log_path = checkpoint_dir / f"k8s_{label}.log"
        _write_command_log(log_path, result)
        out["commands"].append(
            {
                "label": label,
                "argv": argv,
                "returncode": result.returncode,
                "log_path": _display_path(log_path),
            }
        )
        if result.returncode != 0:
            out["status"] = "degraded"
    return out


def _build_start_receipt(
    *,
    run_id: str,
    candidate_id: str,
    provider: str,
    profile: str,
    providers_config: Path,
    config_path: Optional[Path],
    duration_hours: int,
    interval_minutes: int,
) -> Dict[str, Any]:
    tracked = [
        REPO_ROOT / "config" / "defaults.json",
        REPO_ROOT / "config" / "providers.json",
        REPO_ROOT / "config" / "profiles.json",
        REPO_ROOT / "config" / "scoring.v1.json",
        REPO_ROOT / "ops" / "k8s" / "jobintel" / "cronjob.yaml",
        providers_config,
    ]
    config_hashes: Dict[str, Dict[str, Any]] = {}
    for path in tracked:
        rel = _display_path(path)
        if path.exists():
            config_hashes[rel] = {"sha256": _sha256_file(path), "bytes": path.stat().st_size}
        else:
            config_hashes[rel] = {"missing": True}

    return {
        "schema_version": "m21.onprem_stability_harness.start.v1",
        "started_at": _utc_now_iso(),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "provider": provider,
        "profile": profile,
        "duration_hours": duration_hours,
        "interval_minutes": interval_minutes,
        "config_path": _display_path(config_path) if config_path else None,
        "config_hashes": config_hashes,
    }


def _build_pipeline_cmd(provider: str, profile: str, providers_config: Path) -> List[str]:
    return [
        sys.executable,
        "scripts/run_daily.py",
        "--providers",
        provider,
        "--profiles",
        profile,
        "--providers-config",
        str(providers_config),
        "--offline",
        "--snapshot-only",
        "--no_post",
    ]


def _execute_interval(
    *,
    index: int,
    run_id: str,
    candidate_id: str,
    provider: str,
    profile: str,
    providers_config: Path,
    state_dir: Path,
    data_dir: Path,
    receipt_dir: Path,
    namespace: str,
    kube_context: str,
    skip_k8s: bool,
) -> Dict[str, Any]:
    checkpoint_dir = receipt_dir / "checkpoints" / f"checkpoint-{index:03d}"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    interval_run_id = f"{run_id}-i{index:03d}"
    env = os.environ.copy()
    env["JOBINTEL_CANDIDATE_ID"] = candidate_id
    env["JOBINTEL_RUN_ID"] = interval_run_id
    env["JOBINTEL_STATE_DIR"] = str(state_dir)
    env["JOBINTEL_DATA_DIR"] = str(data_dir)

    started = _utc_now_iso()
    start_ts = time.time()
    pipeline_cmd = _build_pipeline_cmd(provider, profile, providers_config)
    pipeline_result = _run_command(pipeline_cmd, env=env)
    runtime_sec = round(time.time() - start_ts, 3)

    pipeline_log = checkpoint_dir / "pipeline.log"
    _write_command_log(pipeline_log, pipeline_result)

    expected = _candidate_runs_dir(state_dir, candidate_id) / sanitize_run_id(interval_run_id)
    run_dir = expected if expected.exists() else _discover_latest_run_dir(state_dir, candidate_id)

    k8s_snapshot = _capture_k8s_snapshot(namespace, kube_context, checkpoint_dir, skip_k8s)

    artifact_hashes: Dict[str, Dict[str, Any]] = {}
    if run_dir and run_dir.exists():
        artifact_hashes = _artifact_hash_summary(run_dir, profile)

    checkpoint = {
        "schema_version": "m21.onprem_stability_harness.checkpoint.v1",
        "interval_index": index,
        "started_at": started,
        "finished_at": _utc_now_iso(),
        "duration_seconds": runtime_sec,
        "jobintel_run_id": interval_run_id,
        "pipeline": {
            "argv": pipeline_cmd,
            "returncode": pipeline_result.returncode,
            "log_path": _display_path(pipeline_log),
        },
        "run_dir": _display_path(run_dir) if run_dir and run_dir.exists() else None,
        "artifact_hash_summary": artifact_hashes,
        "k8s_snapshot": k8s_snapshot,
        "status": "pass" if pipeline_result.returncode == 0 else "fail",
    }
    _write_json(checkpoint_dir / "checkpoint.json", checkpoint)
    return checkpoint


def _resolve_run_dir(path_value: Optional[str]) -> Optional[Path]:
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def _finalize(
    *,
    receipt_dir: Path,
    profile: str,
    baseline_run_dir: Optional[Path],
    latest_success_run_dir: Optional[Path],
    allow_run_id_drift: bool,
) -> Dict[str, Any]:
    final_dir = receipt_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    replay_cmd: List[str] = []
    replay_result: Optional[CommandResult] = None
    if latest_success_run_dir is not None:
        replay_cmd = [
            sys.executable,
            "scripts/replay_run.py",
            "--run-dir",
            str(latest_success_run_dir),
            "--profile",
            profile,
            "--strict",
            "--json",
        ]
        replay_result = _run_command(replay_cmd)
        _write_command_log(final_dir / "replay.log", replay_result)

    snapshot_cmd = [sys.executable, "scripts/verify_snapshots_immutable.py"]
    snapshot_result = _run_command(snapshot_cmd)
    _write_command_log(final_dir / "snapshot_immutability.log", snapshot_result)

    determinism_cmd: List[str] = []
    determinism_result: Optional[CommandResult] = None
    if baseline_run_dir is not None and latest_success_run_dir is not None:
        determinism_cmd = [
            sys.executable,
            "scripts/compare_run_artifacts.py",
            str(baseline_run_dir),
            str(latest_success_run_dir),
            "--repo-root",
            str(REPO_ROOT),
        ]
        if allow_run_id_drift:
            determinism_cmd.append("--allow-run-id-drift")
        determinism_result = _run_command(determinism_cmd)
        _write_command_log(final_dir / "determinism_compare.log", determinism_result)

    fail_reasons: List[str] = []
    if latest_success_run_dir is None:
        fail_reasons.append("no_successful_pipeline_runs")
    if replay_result is None:
        fail_reasons.append("replay_not_executed")
    elif replay_result.returncode != 0:
        fail_reasons.append("replay_failed")
    if snapshot_result.returncode != 0:
        fail_reasons.append("snapshot_immutability_failed")
    if determinism_result is None:
        fail_reasons.append("determinism_compare_not_executed")
    elif determinism_result.returncode != 0:
        fail_reasons.append("determinism_compare_failed")

    return {
        "schema_version": "m21.onprem_stability_harness.final.v1",
        "finished_at": _utc_now_iso(),
        "replay": {
            "argv": replay_cmd,
            "returncode": None if replay_result is None else replay_result.returncode,
            "log_path": _display_path(final_dir / "replay.log") if replay_result else None,
        },
        "snapshot_immutability": {
            "argv": snapshot_cmd,
            "returncode": snapshot_result.returncode,
            "log_path": _display_path(final_dir / "snapshot_immutability.log"),
        },
        "determinism_compare": {
            "argv": determinism_cmd,
            "returncode": None if determinism_result is None else determinism_result.returncode,
            "log_path": _display_path(final_dir / "determinism_compare.log") if determinism_result else None,
            "allow_run_id_drift": allow_run_id_drift,
        },
        "status": "pass" if not fail_reasons else "fail",
        "fail_reasons": fail_reasons,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run M21 on-prem stability harness.")
    parser.add_argument("--duration-hours", type=int, default=72)
    parser.add_argument("--interval-minutes", type=int, default=60)
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--provider", default="")
    parser.add_argument("--profile", default="")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Optional JSON config path.")
    parser.add_argument("--providers-config", default="config/providers.json")
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--data-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--namespace", default=DEFAULT_K8S_NAMESPACE)
    parser.add_argument("--kube-context", default="")
    parser.add_argument("--allow-run-id-drift", action="store_true")
    parser.add_argument("--max-intervals", type=int, default=0, help="Testing/dev override for total intervals.")
    parser.add_argument("--no-sleep", action="store_true", help="Skip interval sleep (for test/dev).")
    parser.add_argument("--skip-k8s", action="store_true", help="Skip kubectl snapshots.")
    args = parser.parse_args(argv)

    if args.duration_hours <= 0:
        raise SystemExit("--duration-hours must be > 0")
    if args.interval_minutes <= 0:
        raise SystemExit("--interval-minutes must be > 0")
    if args.max_intervals < 0:
        raise SystemExit("--max-intervals must be >= 0")

    config_path = Path(args.config).resolve() if args.config else None
    defaults = _maybe_load_defaults(config_path)

    candidate_id = _resolve_candidate(args.candidate_id, defaults)
    provider = args.provider or str(defaults.get("default_provider_id") or "openai")
    profile = args.profile or str(defaults.get("default_profile") or "cs")

    state_dir = _resolve_state_dir(Path(args.state_dir) if args.state_dir else None)
    data_dir = _resolve_data_dir(Path(args.data_dir) if args.data_dir else None)
    providers_config = (REPO_ROOT / args.providers_config).resolve()

    run_id = args.run_id or os.environ.get("JOBINTEL_RUN_ID", "").strip() or _default_run_id()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (state_dir / "proofs" / "m21" / run_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    start_receipt = _build_start_receipt(
        run_id=run_id,
        candidate_id=candidate_id,
        provider=provider,
        profile=profile,
        providers_config=providers_config,
        config_path=config_path if config_path and config_path.exists() else None,
        duration_hours=args.duration_hours,
        interval_minutes=args.interval_minutes,
    )
    _write_json(output_dir / "start_receipt.json", start_receipt)

    total_intervals = (
        args.max_intervals
        if args.max_intervals
        else max(1, int((args.duration_hours * 60 + args.interval_minutes - 1) // args.interval_minutes))
    )

    checkpoints: List[Dict[str, Any]] = []
    successful_run_dirs: List[Path] = []

    for index in range(total_intervals):
        checkpoint = _execute_interval(
            index=index,
            run_id=run_id,
            candidate_id=candidate_id,
            provider=provider,
            profile=profile,
            providers_config=providers_config,
            state_dir=state_dir,
            data_dir=data_dir,
            receipt_dir=output_dir,
            namespace=args.namespace,
            kube_context=args.kube_context,
            skip_k8s=args.skip_k8s,
        )
        checkpoints.append(checkpoint)
        _append_jsonl(output_dir / "checkpoints.jsonl", checkpoint)

        run_dir_str = checkpoint.get("run_dir")
        if checkpoint.get("status") == "pass" and isinstance(run_dir_str, str):
            resolved = _resolve_run_dir(run_dir_str)
            if resolved is not None:
                successful_run_dirs.append(resolved)

        if index < total_intervals - 1 and not args.no_sleep:
            time.sleep(args.interval_minutes * 60)

    baseline_run_dir = successful_run_dirs[0] if successful_run_dirs else None
    latest_success_run_dir = successful_run_dirs[-1] if successful_run_dirs else None

    final_receipt = _finalize(
        receipt_dir=output_dir,
        profile=profile,
        baseline_run_dir=baseline_run_dir,
        latest_success_run_dir=latest_success_run_dir,
        allow_run_id_drift=args.allow_run_id_drift,
    )

    summary = {
        "schema_version": "m21.onprem_stability_harness.summary.v1",
        "run_id": run_id,
        "candidate_id": candidate_id,
        "provider": provider,
        "profile": profile,
        "started_at": start_receipt["started_at"],
        "finished_at": final_receipt["finished_at"],
        "duration_hours": args.duration_hours,
        "interval_minutes": args.interval_minutes,
        "intervals_planned": total_intervals,
        "intervals_completed": len(checkpoints),
        "success_count": sum(1 for item in checkpoints if item.get("status") == "pass"),
        "failure_count": sum(1 for item in checkpoints if item.get("status") != "pass"),
        "checkpoint_receipts": _display_path(output_dir / "checkpoints.jsonl"),
        "final_status": final_receipt["status"],
        "final_fail_reasons": final_receipt["fail_reasons"],
    }

    _write_json(output_dir / "final_receipt.json", final_receipt)
    _write_json(output_dir / "summary.json", summary)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if final_receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
