from __future__ import annotations

import json
from pathlib import Path

import scripts.ops.check_dr_receipt_bundle as checker

PHASE_TEMPLATE = {
    "schema_version": 1,
    "status": "ok",
    "timestamp_utc": "2026-02-27T05:08:53Z",
}


REQUIRED_PHASES = [
    "check_health",
    "restore",
    "validate",
    "notify",
    "request_manual_approval",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_valid_bundle(bundle_dir: Path) -> None:
    for phase in REQUIRED_PHASES:
        _write_json(
            bundle_dir / f"{phase}.json",
            {
                **PHASE_TEMPLATE,
                "phase": phase,
                "payload": {
                    "input": {"action": phase},
                    "result": {"ok": True},
                },
            },
        )

    _write_json(
        bundle_dir / "bringup.json",
        {
            **PHASE_TEMPLATE,
            "phase": "bringup",
            "build_id": "signalcraft-dr-orchestrator-dr-infra:build-123",
            "execution_id": "m19b-success-true-20260227T050707Z",
            "terraform_backend": {
                "bucket": "signalcraft-dr-tfstate",
                "key": "jobintel/dr/terraform/dr-runner.tfstate",
                "dynamodb_table": "signalcraft-dr-tf-lock",
            },
            "terraform_outputs": {},
        },
    )

    _write_json(
        bundle_dir / "alarm-transition-evidence.json",
        {
            "schema_version": 1,
            "kind": "alarm_transition_evidence",
            "required_transition": "OK->ALARM->OK",
            "ok_alarm_ok_sequence_found": True,
            "alarms": [
                {
                    "alarm_name": "signalcraft-dr-orchestrator-pipeline-freshness",
                    "has_ok_alarm_ok_sequence": True,
                    "transitions": [
                        {
                            "timestamp": "2026-02-27T04:00:00+00:00",
                            "from": "OK",
                            "to": "ALARM",
                            "summary": "Alarm updated from OK to ALARM",
                        },
                        {
                            "timestamp": "2026-02-27T05:00:00+00:00",
                            "from": "ALARM",
                            "to": "OK",
                            "summary": "Alarm updated from ALARM to OK",
                        },
                    ],
                }
            ],
        },
    )


def test_checker_accepts_complete_bundle(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_valid_bundle(bundle_dir)

    assert checker.main(["--bundle-dir", str(bundle_dir)]) == 0


def test_checker_fails_when_required_receipt_missing(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_valid_bundle(bundle_dir)
    (bundle_dir / "validate.json").unlink()

    assert checker.main(["--bundle-dir", str(bundle_dir)]) == 1
