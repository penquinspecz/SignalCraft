from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

from ji_engine.artifacts.catalog import assert_no_forbidden_fields
from scripts.schema_validate import resolve_named_schema_path, validate_payload

_FORBIDDEN_KEYS = frozenset({"jd_text", "description", "requirements", "responsibilities"})
_JD_LEAK_MARKER = "UNIQUE_JD_LEAK_MARKER_DO_NOT_SERIALIZE"


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
    return {"data_dir": data_dir, "state_dir": state_dir, "output_dir": output_dir}


def _sample_ranked_jobs() -> list[dict[str, Any]]:
    return [
        {
            "job_id": "job-high",
            "content_fingerprint": "f" * 64,
            "score": 99,
            "score_hits": [
                {"rule": "boost_relevant", "count": 1, "delta": 10},
                {"rule": "penalty_low_level", "count": 1, "delta": -5},
            ],
            "description": f"{_JD_LEAK_MARKER} description text",
            "requirements": f"{_JD_LEAK_MARKER} requirements",
            "responsibilities": f"{_JD_LEAK_MARKER} responsibilities",
            "jd_text": f"{_JD_LEAK_MARKER} jd body",
        },
        {
            "job_id": "job-tie-b",
            "content_fingerprint": "b" * 64,
            "score": 90,
            "score_hits": [{"rule": "boost_maybe", "count": 1, "delta": 5}],
        },
        {
            "job_id": "job-tie-a",
            "content_fingerprint": "a" * 64,
            "score": 90,
            "score_hits": [
                {"rule": "boost_maybe", "count": 1, "delta": 5},
                {"rule": "penalty_irrelevant", "count": 1, "delta": -5},
            ],
            "jd_text": f"{_JD_LEAK_MARKER} repeated",
        },
    ]


def _fake_success_run(run_daily: Any, output_dir: Path):
    ranked_jobs_payload = _sample_ranked_jobs()

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
            targets = (
                (run_daily._provider_ranked_jobs_json("openai", profile), ranked_jobs_payload),
                (run_daily._provider_ranked_jobs_csv("openai", profile), ""),
                (run_daily._provider_ranked_families_json("openai", profile), []),
                (run_daily._provider_shortlist_md("openai", profile), ""),
                (run_daily._provider_top_md("openai", profile), ""),
            )
            for path, payload in targets:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix == ".json":
                    path.write_text(json.dumps(payload), encoding="utf-8")
                else:
                    path.write_text(str(payload), encoding="utf-8")

    return fake_run


def _latest_explanation_path(run_daily: Any) -> Path:
    paths = sorted(run_daily.RUN_METADATA_DIR.glob("*/artifacts/explanation_v1.json"))
    assert paths, "explanation artifact should exist"
    return paths[-1]


def _validate_schema(payload: Dict[str, Any]) -> None:
    schema = json.loads(resolve_named_schema_path("explanation", 1).read_text(encoding="utf-8"))
    errors = validate_payload(payload, schema)
    assert errors == [], f"explanation schema validation failed: {errors}"


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


def _iter_strings(obj: object) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _iter_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_strings(value)


def test_explanation_artifact_v1_written_and_contract_safe(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _setup_env(monkeypatch, tmp_path)

    import ji_engine.config as config
    import scripts.run_daily as run_daily

    config = importlib.reload(config)
    run_daily = importlib.reload(run_daily)
    run_daily.USE_SUBPROCESS = False

    monkeypatch.setattr(run_daily, "_run", _fake_success_run(run_daily, paths["output_dir"]))
    monkeypatch.setattr(sys, "argv", ["run_daily.py", "--no_subprocess", "--profiles", "cs", "--no_post"])

    assert run_daily.main() == 0

    explanation_path = _latest_explanation_path(run_daily)
    payload = json.loads(explanation_path.read_text(encoding="utf-8"))
    _validate_schema(payload)

    assert payload["schema_version"] == "explanation.v1"
    assert payload["candidate_id"] == "local"
    assert payload["top_jobs"], "top_jobs should not be empty for scored input"
    ranks = [item["rank"] for item in payload["top_jobs"]]
    assert ranks == list(range(1, len(ranks) + 1))
    ordered_hashes = [item["job_hash"] for item in payload["top_jobs"][:3]]
    assert ordered_hashes == [("f" * 64), ("a" * 64), ("b" * 64)]

    assert_no_forbidden_fields(payload, context="explanation_v1")
    forbidden = _find_forbidden_keys(payload)
    assert forbidden == []
    serialized = json.dumps(payload, sort_keys=True)
    assert _JD_LEAK_MARKER not in serialized
    assert all(len(value) <= 128 for value in _iter_strings(payload))

    run_reports = sorted(run_daily.RUN_METADATA_DIR.glob("*.json"))
    assert run_reports, "run_report metadata should exist"
    report_payload = json.loads(run_reports[-1].read_text(encoding="utf-8"))
    pointer = report_payload.get("explanation_artifact")
    assert isinstance(pointer, dict)
    assert pointer.get("path", "").endswith("/artifacts/explanation_v1.json")
