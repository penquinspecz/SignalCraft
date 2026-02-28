#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_RECEIPTS: dict[str, tuple[str, ...]] = {
    "check_health": ("check_health.json",),
    "bringup": ("bringup.json", "codebuild-bringup.json"),
    "restore": ("restore.json",),
    "validate": ("validate.json",),
    "notify": ("notify.json",),
    "request_manual_approval": ("request_manual_approval.json",),
}

OPTIONAL_RECEIPTS: dict[str, tuple[str, ...]] = {
    "record_manual_decision": ("record_manual_decision.json",),
}

ALARM_TRANSITION_PATTERN = re.compile(r"Alarm updated from\s+([A-Z_]+)\s+to\s+([A-Z_]+)")


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_required:{path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _parse_transition(item: dict[str, Any]) -> tuple[str, str] | None:
    history_data = item.get("HistoryData")
    if isinstance(history_data, str):
        try:
            decoded = json.loads(history_data)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            old_state = decoded.get("oldState")
            new_state = decoded.get("newState")
            if isinstance(old_state, dict) and isinstance(new_state, dict):
                from_state = old_state.get("stateValue")
                to_state = new_state.get("stateValue")
                if isinstance(from_state, str) and isinstance(to_state, str):
                    return from_state, to_state

    summary = item.get("HistorySummary")
    if isinstance(summary, str):
        match = ALARM_TRANSITION_PATTERN.search(summary)
        if match:
            return match.group(1), match.group(2)
    return None


def _has_ok_alarm_ok_sequence(transitions: list[dict[str, Any]]) -> bool:
    saw_ok_to_alarm = False
    for transition in transitions:
        from_state = transition.get("from")
        to_state = transition.get("to")
        if from_state == "OK" and to_state == "ALARM":
            saw_ok_to_alarm = True
        elif saw_ok_to_alarm and from_state == "ALARM" and to_state == "OK":
            return True
    return False


def _build_alarm_transition_evidence(alarm_history_paths: list[Path]) -> dict[str, Any]:
    alarms: list[dict[str, Any]] = []

    for path in alarm_history_paths:
        payload = _read_json(path)
        items = payload.get("AlarmHistoryItems")
        if not isinstance(items, list):
            raise ValueError(f"missing_alarm_history_items:{_display_path(path)}")

        transitions: list[dict[str, Any]] = []
        alarm_name = ""
        for item in items:
            if not isinstance(item, dict):
                continue
            timestamp = item.get("Timestamp")
            parsed = _parse_transition(item)
            if not isinstance(timestamp, str) or parsed is None:
                continue
            from_state, to_state = parsed
            if not alarm_name and isinstance(item.get("AlarmName"), str):
                alarm_name = str(item["AlarmName"])
            transitions.append(
                {
                    "timestamp": timestamp,
                    "from": from_state,
                    "to": to_state,
                    "summary": str(item.get("HistorySummary", "")),
                }
            )

        if not alarm_name:
            alarm_name = path.stem

        transitions.sort(key=lambda item: _parse_timestamp(str(item["timestamp"])))
        alarms.append(
            {
                "alarm_name": alarm_name,
                "source_path": _display_path(path),
                "transitions": transitions,
                "has_ok_alarm_ok_sequence": _has_ok_alarm_ok_sequence(transitions),
            }
        )

    return {
        "schema_version": 1,
        "kind": "alarm_transition_evidence",
        "required_transition": "OK->ALARM->OK",
        "ok_alarm_ok_sequence_found": any(alarm["has_ok_alarm_ok_sequence"] for alarm in alarms),
        "alarms": alarms,
    }


def _resolve_receipt(source_dir: Path, candidates: tuple[str, ...]) -> Path | None:
    for candidate in candidates:
        path = source_dir / candidate
        if path.exists() and path.is_file():
            return path
    return None


def _copy_receipt(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)


def _build_manifest(output_dir: Path, *, source_dir: Path) -> None:
    files = sorted(
        [path for path in output_dir.iterdir() if path.is_file() and path.name != "bundle-manifest.json"],
        key=lambda path: path.name,
    )
    payload = {
        "schema_version": 1,
        "source_receipts_dir": _display_path(source_dir),
        "required_receipts": list(REQUIRED_RECEIPTS.keys()),
        "optional_receipts": list(OPTIONAL_RECEIPTS.keys()),
        "files": [
            {
                "path": path.name,
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
    }
    _write_json(output_dir / "bundle-manifest.json", payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect DR rehearsal receipts into a normalized, checker-ready bundle directory."
    )
    parser.add_argument("--source-dir", required=True, help="Source directory containing raw phase receipts.")
    parser.add_argument("--output-dir", required=True, help="Destination directory for normalized bundle.")
    parser.add_argument(
        "--alarm-history-json",
        action="append",
        default=[],
        help="Alarm history JSON export (aws cloudwatch describe-alarm-history --output json). Repeatable.",
    )
    parser.add_argument(
        "--alarm-evidence-json",
        default="",
        help="Prebuilt alarm transition evidence JSON. If set, alarm-history-json inputs are ignored.",
    )
    args = parser.parse_args(argv)

    source_dir = Path(args.source_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        raise SystemExit(f"source_dir_not_found:{_display_path(source_dir)}")

    output_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for phase, candidates in REQUIRED_RECEIPTS.items():
        source_path = _resolve_receipt(source_dir, candidates)
        if source_path is None:
            failures.append(f"missing_required_receipt:{phase}:{','.join(candidates)}")
            continue
        _copy_receipt(source_path, output_dir / f"{phase}.json")

    for phase, candidates in OPTIONAL_RECEIPTS.items():
        source_path = _resolve_receipt(source_dir, candidates)
        if source_path is None:
            continue
        _copy_receipt(source_path, output_dir / f"{phase}.json")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    if args.alarm_evidence_json:
        alarm_evidence_path = Path(args.alarm_evidence_json).resolve()
        alarm_evidence = _read_json(alarm_evidence_path)
    else:
        alarm_paths = [Path(path).resolve() for path in args.alarm_history_json]
        if not alarm_paths:
            default_alarm_path = source_dir / "alarm-transition-evidence.json"
            if default_alarm_path.exists() and default_alarm_path.is_file():
                alarm_paths = [default_alarm_path]
        if not alarm_paths:
            print("FAIL: missing_alarm_evidence:provide --alarm-history-json or --alarm-evidence-json")
            return 1
        alarm_evidence = _build_alarm_transition_evidence(alarm_paths)

    _write_json(output_dir / "alarm-transition-evidence.json", alarm_evidence)
    _build_manifest(output_dir, source_dir=source_dir)

    print(f"dr_receipt_bundle_collector_source={_display_path(source_dir)}")
    print(f"dr_receipt_bundle_collector_output={_display_path(output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
