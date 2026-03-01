"""Tests for artifact path boundary validation in publish_s3.py."""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

# Add repo root to path for script imports.
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import scripts.publish_s3 as publish_s3


def _write_json(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_plan(
    *,
    run_id: str,
    run_dir: pathlib.Path,
    verifiable: dict[str, dict[str, str]],
    allow_missing: bool = False,
) -> tuple[list[publish_s3.UploadItem], dict[str, dict[str, str]]]:
    return publish_s3._build_upload_plan(
        run_id=run_id,
        run_dir=run_dir,
        prefix="jobintel",
        candidate_id="local",
        verifiable=verifiable,
        providers=["openai"],
        profiles=["cs"],
        allow_missing=allow_missing,
    )


class TestArtifactPathBoundary:
    """Verify artifact paths from run_report cannot escape allowed roots."""

    def test_traversal_path_rejected(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data_dir = tmp_path / "data"
        state_dir = tmp_path / "state"
        run_dir = state_dir / "runs" / "20260101T000000Z"
        run_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(publish_s3, "DATA_DIR", data_dir)
        monkeypatch.setattr(publish_s3, "STATE_DIR", state_dir)

        verifiable = {"openai:cs:ranked_json": {"path": "../../etc/passwd"}}
        with pytest.raises(SystemExit) as exc:
            _build_plan(run_id="2026-01-01T00:00:00Z", run_dir=run_dir, verifiable=verifiable)
        assert exc.value.code == 2

    def test_absolute_path_outside_roots_rejected(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        data_dir = tmp_path / "data"
        state_dir = tmp_path / "state"
        run_dir = state_dir / "runs" / "20260101T000000Z"
        run_dir.mkdir(parents=True, exist_ok=True)
        outside = tmp_path / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(publish_s3, "DATA_DIR", data_dir)
        monkeypatch.setattr(publish_s3, "STATE_DIR", state_dir)

        verifiable = {"openai:cs:ranked_json": {"path": str(outside)}}
        with pytest.raises(SystemExit) as exc:
            _build_plan(run_id="2026-01-01T00:00:00Z", run_dir=run_dir, verifiable=verifiable)
        assert exc.value.code == 2

    def test_valid_relative_path_accepted(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data_dir = tmp_path / "data"
        state_dir = tmp_path / "state"
        run_dir = state_dir / "runs" / "20260101T000000Z"
        run_dir.mkdir(parents=True, exist_ok=True)
        ranked = data_dir / "openai_ranked_jobs.cs.json"
        ranked.parent.mkdir(parents=True, exist_ok=True)
        ranked.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(publish_s3, "DATA_DIR", data_dir)
        monkeypatch.setattr(publish_s3, "STATE_DIR", state_dir)

        verifiable = {"openai:cs:ranked_json": {"path": ranked.name}}
        uploads, _ = _build_plan(run_id="2026-01-01T00:00:00Z", run_dir=run_dir, verifiable=verifiable)
        assert len(uploads) == 2
        assert all(item.source == ranked.resolve() for item in uploads)

    def test_valid_absolute_path_within_roots_accepted(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        data_dir = tmp_path / "data"
        state_dir = tmp_path / "state"
        run_dir = state_dir / "runs" / "20260101T000000Z"
        run_dir.mkdir(parents=True, exist_ok=True)
        ranked = state_dir / "artifacts" / "openai_ranked_jobs.cs.json"
        ranked.parent.mkdir(parents=True, exist_ok=True)
        ranked.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(publish_s3, "DATA_DIR", data_dir)
        monkeypatch.setattr(publish_s3, "STATE_DIR", state_dir)

        verifiable = {"openai:cs:ranked_json": {"path": str(ranked)}}
        uploads, _ = _build_plan(run_id="2026-01-01T00:00:00Z", run_dir=run_dir, verifiable=verifiable)
        assert len(uploads) == 2
        assert all(item.source == ranked.resolve() for item in uploads)

    def test_symlink_escape_rejected(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data_dir = tmp_path / "data"
        state_dir = tmp_path / "state"
        run_dir = state_dir / "runs" / "20260101T000000Z"
        run_dir.mkdir(parents=True, exist_ok=True)
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir(parents=True, exist_ok=True)
        outside_target = outside_dir / "secret.json"
        outside_target.write_text("{}", encoding="utf-8")

        link = data_dir / "snapshots"
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(outside_dir, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation not supported in this environment")

        monkeypatch.setattr(publish_s3, "DATA_DIR", data_dir)
        monkeypatch.setattr(publish_s3, "STATE_DIR", state_dir)
        verifiable = {"openai:cs:ranked_json": {"path": "snapshots/secret.json"}}
        with pytest.raises(SystemExit) as exc:
            _build_plan(run_id="2026-01-01T00:00:00Z", run_dir=run_dir, verifiable=verifiable)
        assert exc.value.code == 2

    def test_run_dir_outside_state_rejected(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data_dir = tmp_path / "data"
        state_dir = tmp_path / "state"
        outside_run_dir = tmp_path / "outside_runs" / "20260101T000000Z"
        outside_run_dir.mkdir(parents=True, exist_ok=True)
        ranked = data_dir / "openai_ranked_jobs.cs.json"
        ranked.parent.mkdir(parents=True, exist_ok=True)
        ranked.write_text("[]", encoding="utf-8")
        run_id = "2026-01-01T00:00:00Z"
        _write_json(
            outside_run_dir / "run_report.json",
            {
                "run_id": run_id,
                "run_report_schema_version": 1,
                "verifiable_artifacts": {"openai:cs:ranked_json": {"path": ranked.name}},
            },
        )

        monkeypatch.setattr(publish_s3, "DATA_DIR", data_dir)
        monkeypatch.setattr(publish_s3, "STATE_DIR", state_dir)
        monkeypatch.setattr(publish_s3, "RUN_METADATA_DIR", state_dir / "runs")
        with pytest.raises(SystemExit) as exc:
            publish_s3.publish_run(
                run_id=run_id,
                bucket="test-bucket",
                prefix="jobintel",
                run_dir=outside_run_dir,
                dry_run=True,
                require_s3=False,
            )
        assert exc.value.code == 2
