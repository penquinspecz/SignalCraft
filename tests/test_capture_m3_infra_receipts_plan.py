from __future__ import annotations

import json
from pathlib import Path

import scripts.ops.capture_m3_infra_receipts as capture_m3_infra_receipts


def test_plan_mode_is_deterministic_and_does_not_execute_subprocess(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(capture_m3_infra_receipts, "REPO_ROOT", tmp_path)

    run_calls: list[list[str]] = []

    def fail_if_called(cmd, *, cwd=None):  # type: ignore[no-untyped-def]
        run_calls.append(list(cmd))
        raise AssertionError("_run should not be called in plan mode")

    monkeypatch.setattr(capture_m3_infra_receipts, "_run", fail_if_called)

    args = [
        "--run-id",
        "2026-02-07T03:00:00Z",
        "--output-dir",
        "ops/proof/bundles",
        "--cluster-context",
        "ctx-fixed",
        "--namespace",
        "jobintel",
        "--job-name",
        "jobintel-liveproof-20260207",
        "--pod-name",
        "jobintel-liveproof-20260207-abcde",
        "--captured-at",
        "2026-02-07T03:15:00Z",
    ]

    rc_one = capture_m3_infra_receipts.main(args)
    rc_two = capture_m3_infra_receipts.main(args)
    assert rc_one == 0
    assert rc_two == 0
    assert run_calls == []

    infra_dir = tmp_path / "ops" / "proof" / "bundles" / "m3-2026-02-07T03:00:00Z" / "infra"
    assert (infra_dir / "terraform_evidence.log").exists()
    assert (infra_dir / "kubectl_describe_pod.log").exists()
    assert (infra_dir / "kubectl_get_events.log").exists()
    assert (infra_dir / "receipt.json").exists()
    assert (infra_dir / "manifest.json").exists()

    receipt = json.loads((infra_dir / "receipt.json").read_text(encoding="utf-8"))
    assert receipt == {
        "captured_at": "2026-02-07T03:15:00Z",
        "evidence_files": [
            "terraform_evidence.log",
            "kubectl_describe_pod.log",
            "kubectl_get_events.log",
        ],
        "job_name": "jobintel-liveproof-20260207",
        "k8s_context": "ctx-fixed",
        "mode": "plan",
        "namespace": "jobintel",
        "pod_name": "jobintel-liveproof-20260207-abcde",
        "run_id": "2026-02-07T03:00:00Z",
        "schema_version": 1,
    }

    manifest = json.loads((infra_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["run_id"] == "2026-02-07T03:00:00Z"
    assert [item["path"] for item in manifest["files"]] == [
        "kubectl_describe_pod.log",
        "kubectl_get_events.log",
        "receipt.json",
        "terraform_evidence.log",
    ]
    for item in manifest["files"]:
        assert len(item["sha256"]) == 64
        assert item["size_bytes"] > 0
