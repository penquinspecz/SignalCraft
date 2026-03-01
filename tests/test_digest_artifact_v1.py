from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

from ji_engine.artifacts.catalog import assert_no_forbidden_fields
from scripts.schema_validate import resolve_named_schema_path, validate_payload

_JD_LEAK_MARKER = "DIGEST_JD_LEAK_MARKER_DO_NOT_SERIALIZE"
_FORBIDDEN_KEYS = frozenset({"jd_text", "description", "requirements", "responsibilities", "job_description"})


def _setup_env(monkeypatch: Any, tmp_path: Path) -> Dict[str, Path]:
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    output_dir = data_dir / "ashby_cache"
    snapshot_dir = data_dir / "openai_snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "index.html").write_text("<html>snapshot</html>", encoding="utf-8")
    (data_dir / "candidate_profile.json").write_text('{"skills": [], "roles": []}', encoding="utf-8")
    monkeypatch.setenv("JOBINTEL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(state_dir))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    monkeypatch.setenv("JOBINTEL_DIGEST_NOTIFY", "0")
    return {"data_dir": data_dir, "state_dir": state_dir, "output_dir": output_dir}


def _candidate_roots(run_daily: Any) -> list[Path]:
    roots = [run_daily.candidate_state_paths(run_daily.CANDIDATE_ID).runs]
    if run_daily.CANDIDATE_ID == run_daily.DEFAULT_CANDIDATE_ID:
        roots.append(run_daily.RUN_METADATA_DIR)
    return roots


def _latest_artifact_path(run_daily: Any, name: str) -> Path:
    paths = sorted(path for root in _candidate_roots(run_daily) for path in root.glob(f"*/artifacts/{name}"))
    assert paths, f"artifact should exist: {name}"
    return paths[-1]


def _validate_digest_schema(payload: Dict[str, Any]) -> None:
    schema = json.loads(resolve_named_schema_path("digest", 1).read_text(encoding="utf-8"))
    errors = validate_payload(payload, schema)
    assert errors == [], f"digest schema validation failed: {errors}"


def _iter_strings(obj: object) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _iter_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_strings(value)


def _find_forbidden_keys(obj: object, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_str = str(key).lower()
            if key_str in _FORBIDDEN_KEYS:
                found.append(f"{path}.{key}" if path else str(key))
            child = f"{path}.{key}" if path else str(key)
            found.extend(_find_forbidden_keys(value, child))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            found.extend(_find_forbidden_keys(value, f"{path}[{idx}]"))
    return found


def _fake_success_run(run_daily: Any, output_dir: Path, *, title: str):
    ranked_jobs_payload = [
        {
            "job_id": "job-1",
            "content_fingerprint": "1" * 64,
            "title": title,
            "company": "Acme",
            "location": "Remote",
            "apply_url": "https://example.com/jobs/1",
            "score": 93,
            "score_hits": [
                {"rule": "boost_relevant", "count": 1, "delta": 9},
                {"rule": "penalty_low_level", "count": 1, "delta": -2},
            ],
            "description": f"{_JD_LEAK_MARKER} description",
            "jd_text": f"{_JD_LEAK_MARKER} raw jd",
            "requirements": f"{_JD_LEAK_MARKER} requirements",
        }
    ]

    def fake_run(cmd: list[str], *, stage: str) -> None:
        if stage == "scrape":
            (output_dir / "openai_raw_jobs.json").write_text("[]", encoding="utf-8")
            return
        if stage == "classify":
            (output_dir / "openai_labeled_jobs.json").write_text("[]", encoding="utf-8")
            return
        if stage == "enrich":
            (output_dir / "openai_enriched_jobs.json").write_text("[]", encoding="utf-8")
            return
        if stage.startswith("score:"):
            profile = stage.split(":", 1)[1]
            for path in (
                run_daily._provider_ranked_jobs_json("openai", profile),
                run_daily._provider_ranked_jobs_csv("openai", profile),
                run_daily._provider_ranked_families_json("openai", profile),
                run_daily._provider_shortlist_md("openai", profile),
                run_daily._provider_top_md("openai", profile),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix == ".json":
                    path.write_text(
                        json.dumps(ranked_jobs_payload if "ranked_jobs" in path.name else []), encoding="utf-8"
                    )
                else:
                    path.write_text("", encoding="utf-8")

    return fake_run


def test_digest_artifact_deterministic_and_no_jd_leak(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _setup_env(monkeypatch, tmp_path)
    monkeypatch.setenv("JOBINTEL_RUN_ID", "2026-02-28T12:00:00Z")

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    monkeypatch.setattr(run_daily, "_run", _fake_success_run(run_daily, paths["output_dir"], title="Staff Engineer"))
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    assert run_daily.main() == 0
    digest_path = _latest_artifact_path(run_daily, "digest_v1.json")
    receipt_path = _latest_artifact_path(run_daily, "digest_receipt_v1.json")
    first_bytes = digest_path.read_bytes()
    payload = json.loads(first_bytes.decode("utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "digest_receipt.v1"
    assert receipt["quiet_mode"] is True
    assert receipt["notify"]["status"] == "disabled_quiet_mode"

    _validate_digest_schema(payload)
    assert_no_forbidden_fields(payload, context="digest_v1")
    assert payload["quiet_mode"] is True
    assert payload["notify"] == {"requested": False, "attempted": False, "status": "disabled_quiet_mode"}
    assert payload["current_run"]["top_jobs"], "top_jobs should be present"
    assert payload["current_run"]["top_jobs"][0]["title"] == "Staff Engineer"
    assert payload["cadence"]["daily"]["window_days"] == 1
    assert payload["cadence"]["weekly"]["window_days"] == 7
    assert payload["notable_changes"]["thresholds"]["min_skill_token_delta"] == 2
    assert sorted(payload["notable_changes"]["windows"].keys()) == ["last_14_days", "last_30_days", "last_7_days"]
    assert payload["notable_changes"]["windows"]["last_7_days"]["change_event_count"] == 0
    assert payload["notable_changes"]["windows"]["last_7_days"]["notable_changes"] == []
    assert payload["notable_changes"]["windows"]["last_7_days"]["aggregates"] == {"providers": [], "companies": []}

    forbidden = _find_forbidden_keys(payload)
    assert forbidden == []
    serialized = json.dumps(payload, sort_keys=True)
    assert _JD_LEAK_MARKER not in serialized
    assert all(len(value) <= 512 for value in _iter_strings(payload))

    run_daily.LOCK_PATH.unlink(missing_ok=True)
    run_daily.LAST_RUN_JSON.unlink(missing_ok=True)
    assert run_daily.main() == 0
    second_bytes = digest_path.read_bytes()
    assert first_bytes == second_bytes


def test_digest_candidate_isolation(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _setup_env(monkeypatch, tmp_path)

    def run_for(candidate_id: str, run_id: str, title: str) -> Dict[str, Any]:
        monkeypatch.setenv("JOBINTEL_CANDIDATE_ID", candidate_id)
        monkeypatch.setenv("JOBINTEL_RUN_ID", run_id)

        import ji_engine.config as config
        import scripts.run_daily as run_daily

        config = importlib.reload(config)
        run_daily = importlib.reload(run_daily)
        run_daily.USE_SUBPROCESS = False

        candidate_profile = run_daily.candidate_state_paths(candidate_id).profile_path
        candidate_profile.parent.mkdir(parents=True, exist_ok=True)
        candidate_profile.write_text('{"skills": [], "roles": []}', encoding="utf-8")

        monkeypatch.setattr(run_daily, "_run", _fake_success_run(run_daily, paths["output_dir"], title=title))
        monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

        assert run_daily.main() == 0
        run_daily.LOCK_PATH.unlink(missing_ok=True)
        digest_path = _latest_artifact_path(run_daily, "digest_v1.json")
        payload = json.loads(digest_path.read_text(encoding="utf-8"))
        _validate_digest_schema(payload)
        return {
            "path": digest_path,
            "payload": payload,
        }

    alpha = run_for("alpha", "2026-02-28T13:00:00Z", "Alpha Engineer")
    beta = run_for("beta", "2026-02-28T14:00:00Z", "Beta Engineer")

    assert alpha["payload"]["candidate_id"] == "alpha"
    assert beta["payload"]["candidate_id"] == "beta"
    assert "/candidates/alpha/runs/" in alpha["path"].as_posix()
    assert "/candidates/beta/runs/" in beta["path"].as_posix()
    assert alpha["payload"]["current_run"]["top_jobs"][0]["title"] == "Alpha Engineer"
    assert beta["payload"]["current_run"]["top_jobs"][0]["title"] == "Beta Engineer"
    assert "notable_changes" in alpha["payload"]
    assert "notable_changes" in beta["payload"]
