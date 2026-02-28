#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_PHASES = [
    "check_health",
    "bringup",
    "restore",
    "validate",
    "notify",
    "request_manual_approval",
]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_object_required")
    return payload


def _check_common_phase_fields(payload: dict[str, Any], *, expected_phase: str) -> list[str]:
    failures: list[str] = []
    for field in ("schema_version", "phase", "status", "timestamp_utc"):
        if field not in payload:
            failures.append(f"missing_field:{field}")
    if payload.get("phase") != expected_phase:
        failures.append(f"phase_mismatch:expected={expected_phase}:actual={payload.get('phase')}")
    return failures


def _check_payload_phase(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    phase_payload = payload.get("payload")
    if not isinstance(phase_payload, dict):
        return ["missing_field:payload"]
    if not isinstance(phase_payload.get("input"), dict):
        failures.append("missing_field:payload.input")
    if not isinstance(phase_payload.get("result"), dict):
        failures.append("missing_field:payload.result")
    return failures


def _check_bringup_phase(payload: dict[str, Any]) -> list[str]:
    failures = _check_common_phase_fields(payload, expected_phase="bringup")
    if "build_id" not in payload:
        failures.append("missing_field:build_id")
    if not isinstance(payload.get("terraform_backend"), dict):
        failures.append("missing_field:terraform_backend")
    if "terraform_outputs" not in payload:
        failures.append("missing_field:terraform_outputs")
    return failures


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


def _check_alarm_evidence(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    if payload.get("schema_version") != 1:
        failures.append("alarm_evidence_invalid_schema_version")

    alarms = payload.get("alarms")
    if not isinstance(alarms, list) or not alarms:
        failures.append("alarm_evidence_missing_alarms")
        return failures

    sequence_found = False
    for index, alarm in enumerate(alarms):
        if not isinstance(alarm, dict):
            failures.append(f"alarm_entry_not_object:index={index}")
            continue
        if not isinstance(alarm.get("alarm_name"), str) or not alarm.get("alarm_name"):
            failures.append(f"alarm_name_missing:index={index}")

        transitions = alarm.get("transitions")
        if not isinstance(transitions, list):
            failures.append(f"alarm_transitions_missing:index={index}")
            continue

        transition_objects = [item for item in transitions if isinstance(item, dict)]
        if len(transition_objects) != len(transitions):
            failures.append(f"alarm_transition_entry_not_object:index={index}")

        for transition_index, transition in enumerate(transition_objects):
            if not isinstance(transition.get("timestamp"), str):
                failures.append(f"alarm_transition_missing_timestamp:index={index}:{transition_index}")
            if not isinstance(transition.get("from"), str):
                failures.append(f"alarm_transition_missing_from:index={index}:{transition_index}")
            if not isinstance(transition.get("to"), str):
                failures.append(f"alarm_transition_missing_to:index={index}:{transition_index}")

        has_sequence = _has_ok_alarm_ok_sequence(transition_objects)
        declared_has_sequence = alarm.get("has_ok_alarm_ok_sequence")
        if declared_has_sequence is not None and declared_has_sequence != has_sequence:
            failures.append(f"alarm_transition_sequence_mismatch:index={index}")

        if has_sequence:
            sequence_found = True

    if payload.get("ok_alarm_ok_sequence_found") is not True:
        failures.append("alarm_evidence_flag_not_true")
    if not sequence_found:
        failures.append("alarm_evidence_missing_required_sequence:OK->ALARM->OK")

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate normalized DR receipt bundle completeness and shape.")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument(
        "--require-record-manual-decision",
        action="store_true",
        help="Also require record_manual_decision.json.",
    )
    args = parser.parse_args(argv)

    bundle_dir = Path(args.bundle_dir).resolve()
    if not bundle_dir.exists() or not bundle_dir.is_dir():
        print(f"FAIL: bundle_dir_not_found:{bundle_dir.as_posix()}")
        return 1

    failures: list[str] = []

    for phase in REQUIRED_PHASES:
        path = bundle_dir / f"{phase}.json"
        if not path.exists():
            failures.append(f"missing_required_receipt:{phase}")
            continue
        try:
            payload = _read_json(path)
        except Exception as exc:  # pragma: no cover - defensive
            failures.append(f"invalid_json:{phase}:{exc}")
            continue

        phase_failures = _check_common_phase_fields(payload, expected_phase=phase)
        if phase == "bringup":
            phase_failures = _check_bringup_phase(payload)
        else:
            phase_failures.extend(_check_payload_phase(payload))

        for failure in phase_failures:
            failures.append(f"{phase}:{failure}")

    if args.require_record_manual_decision and not (bundle_dir / "record_manual_decision.json").exists():
        failures.append("missing_required_receipt:record_manual_decision")

    alarm_path = bundle_dir / "alarm-transition-evidence.json"
    if not alarm_path.exists():
        failures.append("missing_required_receipt:alarm-transition-evidence")
    else:
        try:
            alarm_payload = _read_json(alarm_path)
            failures.extend(_check_alarm_evidence(alarm_payload))
        except Exception as exc:  # pragma: no cover - defensive
            failures.append(f"invalid_json:alarm-transition-evidence:{exc}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(f"PASS: dr_receipt_bundle_check:{bundle_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
