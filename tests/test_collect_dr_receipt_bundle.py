from __future__ import annotations

import json
from pathlib import Path

import scripts.ops.collect_dr_receipt_bundle as collect

PHASE_TEMPLATE = {
    "schema_version": 1,
    "status": "ok",
    "timestamp_utc": "2026-02-27T05:08:53Z",
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_required_receipts(source_dir: Path) -> None:
    for phase in ["check_health", "restore", "validate", "notify", "request_manual_approval"]:
        payload = {
            **PHASE_TEMPLATE,
            "phase": phase,
            "payload": {
                "input": {"action": phase},
                "result": {"ok": True},
            },
        }
        _write_json(source_dir / f"{phase}.json", payload)

    _write_json(
        source_dir / "codebuild-bringup.json",
        {
            **PHASE_TEMPLATE,
            "phase": "bringup",
            "build_id": "build-123",
            "execution_id": "m19b-success-true-20260227T050707Z",
            "terraform_backend": {
                "bucket": "signalcraft-dr-tfstate",
                "key": "jobintel/dr/terraform/dr-runner.tfstate",
                "dynamodb_table": "signalcraft-dr-tf-lock",
            },
            "terraform_outputs": {},
        },
    )


def test_collector_normalizes_bundle_and_alarm_evidence(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "bundle"
    _write_required_receipts(source_dir)

    alarm_history = {
        "AlarmHistoryItems": [
            {
                "AlarmName": "signalcraft-dr-orchestrator-pipeline-freshness",
                "Timestamp": "2026-02-27T05:00:00+00:00",
                "HistorySummary": "Alarm updated from ALARM to OK",
                "HistoryData": json.dumps(
                    {
                        "oldState": {"stateValue": "ALARM"},
                        "newState": {"stateValue": "OK"},
                    }
                ),
            },
            {
                "AlarmName": "signalcraft-dr-orchestrator-pipeline-freshness",
                "Timestamp": "2026-02-27T04:00:00+00:00",
                "HistorySummary": "Alarm updated from OK to ALARM",
                "HistoryData": json.dumps(
                    {
                        "oldState": {"stateValue": "OK"},
                        "newState": {"stateValue": "ALARM"},
                    }
                ),
            },
        ]
    }
    alarm_history_path = tmp_path / "alarm-history.json"
    _write_json(alarm_history_path, alarm_history)

    args = [
        "--source-dir",
        str(source_dir),
        "--output-dir",
        str(output_dir),
        "--alarm-history-json",
        str(alarm_history_path),
    ]

    assert collect.main(args) == 0
    first_manifest = (output_dir / "bundle-manifest.json").read_text(encoding="utf-8")

    # Running a second time with identical inputs should produce the same manifest bytes.
    assert collect.main(args) == 0
    second_manifest = (output_dir / "bundle-manifest.json").read_text(encoding="utf-8")

    assert first_manifest == second_manifest
    assert (output_dir / "bringup.json").exists()
    assert not (output_dir / "codebuild-bringup.json").exists()

    alarm_evidence = json.loads((output_dir / "alarm-transition-evidence.json").read_text(encoding="utf-8"))
    assert alarm_evidence["ok_alarm_ok_sequence_found"] is True
    assert alarm_evidence["alarms"][0]["has_ok_alarm_ok_sequence"] is True
