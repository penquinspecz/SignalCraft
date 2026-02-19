from __future__ import annotations

import json
from pathlib import Path

from ji_engine.ai.insights_input import build_weekly_insights_input
from ji_engine.run_repository import FileSystemRunRepository


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_run(
    runs_dir: Path,
    *,
    run_id: str,
    profile: str,
    provider: str,
    ranked_jobs: list[dict[str, object]],
    delta_counts: dict[str, int],
) -> None:
    run_name = run_id.replace(":", "").replace("-", "").replace(".", "")
    run_dir = runs_dir / run_name
    ranked_path = run_dir / provider / profile / f"{provider}_ranked_jobs.{profile}.json"
    _write_json(ranked_path, ranked_jobs)

    run_report = {
        "run_report_schema_version": 1,
        "run_id": run_id,
        "outputs_by_provider": {
            provider: {profile: {"ranked_json": {"path": ranked_path.as_posix(), "sha256": None, "bytes": None}}}
        },
        "delta_summary": {
            "provider_profile": {
                provider: {
                    profile: {
                        "new_job_count": delta_counts["new"],
                        "changed_job_count": delta_counts["changed"],
                        "removed_job_count": delta_counts["removed"],
                        "ranked_total": delta_counts["total"],
                    }
                }
            }
        },
    }
    _write_json(run_dir / "run_report.json", run_report)

    index_payload = {
        "run_id": run_id,
        "timestamp": run_id,
        "providers": {provider: {"profiles": {profile: {"artifacts": {}}}, "artifacts": {}}},
        "artifacts": {"run_report.json": "run_report.json"},
        "run_report_path": "run_report.json",
    }
    _write_json(run_dir / "index.json", index_payload)


def test_ai_insights_trends_are_deterministic_across_windows(tmp_path: Path) -> None:
    runs_dir = tmp_path / "state" / "runs"
    provider = "openai"
    profile = "cs"

    _write_run(
        runs_dir,
        run_id="2026-01-05T00:00:00Z",
        profile=profile,
        provider=provider,
        ranked_jobs=[{"job_id": "r4a", "title": "Engineer", "company": "Delta", "location": "NYC", "score": 70}],
        delta_counts={"new": 2, "changed": 0, "removed": 1, "total": 5},
    )
    _write_run(
        runs_dir,
        run_id="2026-01-18T00:00:00Z",
        profile=profile,
        provider=provider,
        ranked_jobs=[
            {"job_id": "r3a", "title": "Engineer", "company": "Beta", "location": "NYC", "score": 79},
            {"job_id": "r3b", "title": "Analyst", "company": "Gamma", "location": "SF", "score": 75},
        ],
        delta_counts={"new": 0, "changed": 1, "removed": 2, "total": 7},
    )
    _write_run(
        runs_dir,
        run_id="2026-01-26T00:00:00Z",
        profile=profile,
        provider=provider,
        ranked_jobs=[
            {"job_id": "r2a", "title": "Engineer", "company": "Alpha", "location": "Remote", "score": 81},
            {"job_id": "r2b", "title": "PM", "company": "Gamma", "location": "SF", "score": 80},
        ],
        delta_counts={"new": 1, "changed": 2, "removed": 1, "total": 8},
    )
    _write_run(
        runs_dir,
        run_id="2026-01-30T00:00:00Z",
        profile=profile,
        provider=provider,
        ranked_jobs=[
            {"job_id": "r1a", "title": "Engineer", "company": "Alpha", "location": "Remote", "score": 90},
            {"job_id": "r1b", "title": "Architect", "company": "Beta", "location": "NYC", "score": 88},
        ],
        delta_counts={"new": 3, "changed": 1, "removed": 0, "total": 10},
    )

    repo = FileSystemRunRepository(runs_dir)
    repo.rebuild_index("local")

    ranked_path = runs_dir / "20260130T000000Z" / provider / profile / f"{provider}_ranked_jobs.{profile}.json"
    prev_path = runs_dir / "20260126T000000Z" / provider / profile / f"{provider}_ranked_jobs.{profile}.json"

    _, payload = build_weekly_insights_input(
        provider=provider,
        profile=profile,
        ranked_path=ranked_path,
        prev_path=prev_path,
        ranked_families_path=None,
        run_id="2026-01-30T00:00:00Z",
        run_metadata_dir=runs_dir,
        run_repository=repo,
    )

    windows = payload["trend_analysis"]["windows"]
    by_days = {item["window_days"]: item for item in windows}

    assert sorted(by_days.keys()) == [7, 14, 30]
    assert by_days[7]["runs_considered"] == 2
    assert by_days[14]["runs_considered"] == 3
    assert by_days[30]["runs_considered"] == 4

    assert by_days[7]["job_counts"] == {"new": 4, "changed": 3, "removed": 1, "total": 18}
    assert by_days[14]["job_counts"] == {"new": 4, "changed": 4, "removed": 3, "total": 25}
    assert by_days[30]["job_counts"] == {"new": 6, "changed": 4, "removed": 4, "total": 30}

    company_growth_7 = by_days[7]["company_growth"]
    assert company_growth_7
    assert company_growth_7[0]["name"] == "Beta"
    assert company_growth_7[0]["delta"] == 1
