#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

CANONICAL_JSON_KWARGS = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")}
VOLATILE_VALUE_KEYS = {
    "created_at",
    "created_at_utc",
    "ended_at",
    "fetched_at",
    "generated_at_utc",
    "run_started_at",
    "scored_at",
    "scraped_at",
    "started_at",
    "timestamp",
    "updated_at",
    "duration_sec",
}
RUN_SUMMARY_DROP_KEYS = {"created_at_utc", "git_sha", "quicklinks"}
RUN_HEALTH_DROP_KEYS = {"timestamps", "durations", "logs", "proof_bundle_path"}
PROVIDER_AVAILABILITY_DROP_KEYS = {"generated_at_utc"}
IDENTITY_DIFF_DROP_KEYS = {"generated_at", "generated_at_utc"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, **CANONICAL_JSON_KWARGS)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _normalize_recursive(value: Any, *, drop_run_id: bool) -> Any:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, child in value.items():
            if key in VOLATILE_VALUE_KEYS:
                continue
            if drop_run_id and key == "run_id":
                continue
            out[key] = _normalize_recursive(child, drop_run_id=drop_run_id)
        return out
    if isinstance(value, list):
        return [_normalize_recursive(item, drop_run_id=drop_run_id) for item in value]
    return value


def _normalize_run_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    value = dict(payload)
    for key in RUN_SUMMARY_DROP_KEYS:
        value.pop(key, None)
    return _normalize_recursive(value, drop_run_id=True)


def _normalize_run_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    value = dict(payload)
    for key in RUN_HEALTH_DROP_KEYS:
        value.pop(key, None)
    return _normalize_recursive(value, drop_run_id=True)


def _normalize_provider_availability(payload: Dict[str, Any]) -> Dict[str, Any]:
    value = dict(payload)
    for key in PROVIDER_AVAILABILITY_DROP_KEYS:
        value.pop(key, None)
    return _normalize_recursive(value, drop_run_id=True)


def _normalize_identity_diff(payload: Dict[str, Any]) -> Dict[str, Any]:
    value = dict(payload)
    for key in IDENTITY_DIFF_DROP_KEYS:
        value.pop(key, None)
    return _normalize_recursive(value, drop_run_id=True)


def _resolve_artifact_path(path_text: str, *, run_dir: Path, repo_root: Path) -> Path:
    path = Path(path_text)
    candidates: List[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append(run_dir / path)
        candidates.append(repo_root / path)
        if len(path.parts) == 1:
            candidates.append(run_dir / "artifacts" / path)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    raise FileNotFoundError(f"unable to resolve artifact path: {path_text}")


def _required_run_paths(run_dir: Path) -> Dict[str, Path]:
    paths = {
        "run_summary": run_dir / "run_summary.v1.json",
        "run_health": run_dir / "run_health.v1.json",
        "provider_availability": run_dir / "artifacts" / "provider_availability_v1.json",
        "identity_diff": run_dir / "diff.json",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing required artifact(s) in {run_dir}: {', '.join(sorted(missing))}")
    return paths


def _hash_manifest(run_dir: Path, *, repo_root: Path) -> Dict[str, str]:
    required = _required_run_paths(run_dir)
    run_summary = _load_json(required["run_summary"])
    run_health = _load_json(required["run_health"])
    provider_availability = _load_json(required["provider_availability"])
    identity_diff = _load_json(required["identity_diff"])

    if not isinstance(run_summary, dict) or not isinstance(run_health, dict):
        raise ValueError(f"run_summary/run_health must be JSON objects for run_dir={run_dir}")
    if not isinstance(provider_availability, dict) or not isinstance(identity_diff, dict):
        raise ValueError(f"provider_availability/diff.json must be JSON objects for run_dir={run_dir}")

    manifest: Dict[str, str] = {
        "run_health.normalized_sha256": _sha256_text(_canonical_json(_normalize_run_health(run_health))),
        "provider_availability.normalized_sha256": _sha256_text(
            _canonical_json(_normalize_provider_availability(provider_availability))
        ),
        "identity_diff.normalized_sha256": _sha256_text(_canonical_json(_normalize_identity_diff(identity_diff))),
    }

    ranked_outputs = run_summary.get("ranked_outputs")
    if not isinstance(ranked_outputs, dict):
        raise ValueError("run_summary.ranked_outputs missing or invalid")
    for kind in ("ranked_json", "ranked_csv", "ranked_families_json"):
        entries = ranked_outputs.get(kind)
        if not isinstance(entries, list):
            raise ValueError(f"run_summary.ranked_outputs.{kind} missing or invalid")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"run_summary.ranked_outputs.{kind} entry must be object")
            provider = entry.get("provider")
            profile = entry.get("profile")
            path_text = entry.get("path")
            if not isinstance(provider, str) or not isinstance(profile, str) or not isinstance(path_text, str):
                raise ValueError(f"run_summary.ranked_outputs.{kind} missing provider/profile/path")
            resolved = _resolve_artifact_path(path_text, run_dir=run_dir, repo_root=repo_root)
            key = f"{kind}:{provider}:{profile}.sha256"
            manifest[key] = _sha256_file(resolved)
    return {key: manifest[key] for key in sorted(manifest)}


def _build_fixture_data_dir(repo_root: Path, fixture_root: Path) -> Tuple[Path, Path]:
    source_snapshot = repo_root / "data" / "openai_snapshots" / "index.html"
    source_profile = repo_root / "data" / "candidate_profile.json"
    if not source_snapshot.exists():
        raise FileNotFoundError(f"missing pinned snapshot fixture: {source_snapshot}")
    if not source_profile.exists():
        raise FileNotFoundError(f"missing pinned candidate fixture: {source_profile}")

    data_dir = fixture_root / "data"
    snapshot_dir = data_dir / "openai_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_snapshot, snapshot_dir / "index.html")
    shutil.copy2(source_profile, data_dir / "candidate_profile.json")
    return data_dir, source_profile


def _find_run_dir(state_dir: Path, run_id: str) -> Path:
    candidates: List[Path] = []
    for report_path in state_dir.rglob("run_report.json"):
        try:
            payload = _load_json(report_path)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            candidates.append(report_path.parent)
    if not candidates:
        raise FileNotFoundError(f"unable to resolve run_dir for run_id={run_id} under {state_dir}")
    candidates.sort()
    return candidates[-1]


def _parse_run_id(stdout: str) -> Optional[str]:
    for line in stdout.splitlines():
        if line.startswith("JOBINTEL_RUN_ID="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    return None


def _run_once(
    *,
    repo_root: Path,
    fixture_root: Path,
    provider: str,
    profile: str,
    sequence: int,
) -> Tuple[str, Path, Dict[str, Any]]:
    data_dir, profile_source = _build_fixture_data_dir(repo_root, fixture_root)
    state_dir = fixture_root / "state"
    candidate_input_dir = state_dir / "candidates" / "local" / "inputs"
    candidate_input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(profile_source, candidate_input_dir / "candidate_profile.json")

    run_id = f"replay-canary-{sequence:02d}"
    env = os.environ.copy()
    env.update(
        {
            "JOBINTEL_DATA_DIR": str(data_dir),
            "JOBINTEL_STATE_DIR": str(state_dir),
            "JOBINTEL_PROVIDER_ID": provider,
            "CAREERS_MODE": "SNAPSHOT",
            "DISCORD_WEBHOOK_URL": "",
            "JOBINTEL_RUN_ID": run_id,
            "PYTHONPATH": str(repo_root / "src"),
        }
    )
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "run_daily.py"),
        "--no_subprocess",
        "--offline",
        "--providers",
        provider,
        "--profiles",
        profile,
        "--no_post",
    ]
    proc = subprocess.run(cmd, cwd=repo_root, env=env, text=True, capture_output=True, check=False)
    parsed_run_id = _parse_run_id(proc.stdout) or run_id
    run_dir = _find_run_dir(state_dir, parsed_run_id)
    run_result = {
        "exit_code": proc.returncode,
        "run_id": parsed_run_id,
        "run_dir": str(run_dir),
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-6000:],
    }
    if proc.returncode != 0:
        raise RuntimeError(f"run_daily failed (sequence={sequence}, exit_code={proc.returncode})")
    return parsed_run_id, run_dir, run_result


def _compare_identity_diff(left_run_dir: Path, right_run_dir: Path) -> Tuple[bool, Optional[str]]:
    left_path = left_run_dir / "diff.json"
    right_path = right_run_dir / "diff.json"
    if not left_path.exists() or not right_path.exists():
        return False, "missing diff.json identity artifact in one or both runs"
    left_payload = _load_json(left_path)
    right_payload = _load_json(right_path)
    if not isinstance(left_payload, dict) or not isinstance(right_payload, dict):
        return False, "identity diff artifact is not a JSON object"
    left_norm = _normalize_identity_diff(left_payload)
    right_norm = _normalize_identity_diff(right_payload)
    if _canonical_json(left_norm) != _canonical_json(right_norm):
        return False, "identity normalization artifact differs after volatility normalization"
    return True, None


def _compare_provider_availability(left_run_dir: Path, right_run_dir: Path) -> Tuple[bool, Optional[str]]:
    left_path = left_run_dir / "artifacts" / "provider_availability_v1.json"
    right_path = right_run_dir / "artifacts" / "provider_availability_v1.json"
    if not left_path.exists() or not right_path.exists():
        return False, "missing provider_availability_v1.json in one or both runs"
    left_payload = _load_json(left_path)
    right_payload = _load_json(right_path)
    if not isinstance(left_payload, dict) or not isinstance(right_payload, dict):
        return False, "provider_availability artifact is not a JSON object"
    left_norm = _normalize_provider_availability(left_payload)
    right_norm = _normalize_provider_availability(right_payload)
    if _canonical_json(left_norm) != _canonical_json(right_norm):
        return False, "provider_availability differs after volatility normalization"
    return True, None


def _compare_hash_manifests(left_manifest: Dict[str, str], right_manifest: Dict[str, str]) -> List[str]:
    mismatches: List[str] = []
    keys = sorted(set(left_manifest.keys()) | set(right_manifest.keys()))
    for key in keys:
        left_value = left_manifest.get(key)
        right_value = right_manifest.get(key)
        if left_value != right_value:
            mismatches.append(f"{key}: {left_value!r} != {right_value!r}")
    return mismatches


def _run_compare_run_artifacts(repo_root: Path, left_run_dir: Path, right_run_dir: Path) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "compare_run_artifacts.py"),
        str(left_run_dir),
        str(right_run_dir),
        "--allow-run-id-drift",
        "--repo-root",
        str(repo_root),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    proc = subprocess.run(cmd, cwd=repo_root, env=env, text=True, capture_output=True, check=False)
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "command": cmd,
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic fixture replay canary twice and detect drift.")
    parser.add_argument("--provider", default="openai", help="Provider ID to run (default: openai)")
    parser.add_argument("--profile", default="cs", help="Profile to run (default: cs)")
    parser.add_argument(
        "--work-dir",
        default="",
        help="Optional work directory. Defaults to a temporary directory that is cleaned up.",
    )
    parser.add_argument(
        "--diff-out",
        default="artifacts/replay-drift-canary/replay_drift_diff.json",
        help="Path for machine-readable drift diff artifact JSON.",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep the canary work directory after execution for debugging.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    if args.work_dir:
        work_dir = Path(args.work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        work_dir = Path(tempfile.mkdtemp(prefix="jobintel_replay_drift_canary_")).resolve()
        cleanup = not args.keep_work_dir

    diff_out = Path(args.diff_out).resolve()
    diff_out.parent.mkdir(parents=True, exist_ok=True)

    result: Dict[str, Any] = {
        "schema_version": 1,
        "canary": "replay_drift",
        "generated_at_utc": _utc_now(),
        "repo_root": str(repo_root),
        "work_dir": str(work_dir),
        "provider": args.provider,
        "profile": args.profile,
        "status": "fail",
        "checks": {},
        "issues": [],
    }

    try:
        left_run_id, left_run_dir, left_result = _run_once(
            repo_root=repo_root,
            fixture_root=work_dir / "left",
            provider=args.provider,
            profile=args.profile,
            sequence=1,
        )
        right_run_id, right_run_dir, right_result = _run_once(
            repo_root=repo_root,
            fixture_root=work_dir / "right",
            provider=args.provider,
            profile=args.profile,
            sequence=2,
        )

        result["runs"] = {
            "left": {"run_id": left_run_id, "run_dir": str(left_run_dir), **left_result},
            "right": {"run_id": right_run_id, "run_dir": str(right_run_dir), **right_result},
        }

        left_manifest = _hash_manifest(left_run_dir, repo_root=repo_root)
        right_manifest = _hash_manifest(right_run_dir, repo_root=repo_root)
        hash_mismatches = _compare_hash_manifests(left_manifest, right_manifest)
        result["checks"]["artifact_hashes"] = {
            "status": "pass" if not hash_mismatches else "fail",
            "left": left_manifest,
            "right": right_manifest,
            "mismatches": hash_mismatches,
        }
        if hash_mismatches:
            result["issues"].append("artifact hash mismatch detected")

        identity_ok, identity_issue = _compare_identity_diff(left_run_dir, right_run_dir)
        result["checks"]["identity_normalization"] = {
            "status": "pass" if identity_ok else "fail",
            "issue": identity_issue,
        }
        if identity_issue:
            result["issues"].append(identity_issue)

        availability_ok, availability_issue = _compare_provider_availability(left_run_dir, right_run_dir)
        result["checks"]["provider_availability"] = {
            "status": "pass" if availability_ok else "fail",
            "issue": availability_issue,
        }
        if availability_issue:
            result["issues"].append(availability_issue)

        compare_result = _run_compare_run_artifacts(repo_root, left_run_dir, right_run_dir)
        result["checks"]["compare_run_artifacts"] = {
            "status": "pass" if compare_result["exit_code"] == 0 else "fail",
            **compare_result,
        }
        if compare_result["exit_code"] != 0:
            result["issues"].append("compare_run_artifacts detected deterministic drift")

        result["status"] = "pass" if not result["issues"] else "fail"
        _write_json(diff_out, result)
        if result["status"] != "pass":
            print(f"FAIL: replay drift canary detected issues; see {diff_out}")
            return 1
        print(f"PASS: replay drift canary matched deterministic outputs; receipt={diff_out}")
        return 0
    except Exception as exc:
        result["issues"].append(f"canary execution error: {exc}")
        result["status"] = "fail"
        _write_json(diff_out, result)
        print(f"FAIL: replay drift canary execution failed; see {diff_out}")
        return 1
    finally:
        if cleanup:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
