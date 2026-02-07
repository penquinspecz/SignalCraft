from __future__ import annotations

import json
from pathlib import Path

import scripts.ops.prove_m3_backoff_cb as prove_m3_backoff_cb


def test_plan_mode_is_deterministic_and_no_kubectl_calls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(prove_m3_backoff_cb, "REPO_ROOT", tmp_path)

    run_calls: list[list[str]] = []

    def fail_if_called(cmd, *, cwd=None):  # type: ignore[no-untyped-def]
        run_calls.append(list(cmd))
        raise AssertionError("_run should not be called in plan mode")

    monkeypatch.setattr(prove_m3_backoff_cb, "_run", fail_if_called)

    args = [
        "--run-id",
        "2026-02-07T04:00:00Z",
        "--output-dir",
        "ops/proof/bundles",
        "--cluster-context",
        "ctx-fixed",
        "--namespace",
        "jobintel",
        "--template",
        "ops/k8s/jobintel/jobs/jobintel-politeness-proof.job.yaml",
        "--provider-id",
        "proof_backoff",
        "--captured-at",
        "2026-02-07T04:05:00Z",
    ]

    assert prove_m3_backoff_cb.main(args) == 0
    assert prove_m3_backoff_cb.main(args) == 0
    assert run_calls == []

    proof_dir = tmp_path / "ops" / "proof" / "bundles" / "m3-2026-02-07T04:00:00Z" / "politeness"
    assert (proof_dir / "run.log").exists()
    assert (proof_dir / "provenance.json").exists()
    assert (proof_dir / "receipt.json").exists()
    assert (proof_dir / "manifest.json").exists()

    receipt = json.loads((proof_dir / "receipt.json").read_text(encoding="utf-8"))
    assert receipt == {
        "captured_at": "2026-02-07T04:05:00Z",
        "evidence_files": ["run.log", "provenance.json"],
        "k8s_context": "ctx-fixed",
        "mode": "plan",
        "namespace": "jobintel",
        "provider_id": "proof_backoff",
        "run_id": "2026-02-07T04:00:00Z",
        "schema_version": 1,
    }

    manifest = json.loads((proof_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["run_id"] == "2026-02-07T04:00:00Z"
    assert [item["path"] for item in manifest["files"]] == [
        "provenance.json",
        "receipt.json",
        "run.log",
    ]
    for item in manifest["files"]:
        assert len(item["sha256"]) == 64
        assert item["size_bytes"] > 0
