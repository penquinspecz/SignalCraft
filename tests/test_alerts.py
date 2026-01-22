from jobintel.alerts import build_last_seen, compute_alerts, stable_title_location_hash


def test_alerts_new_removed() -> None:
    prev_jobs = [
        {"job_id": "a", "title": "Alpha", "location": "SF", "score": 50},
        {"job_id": "b", "title": "Beta", "location": "NY", "score": 60},
    ]
    curr_jobs = [
        {"job_id": "b", "title": "Beta", "location": "NY", "score": 60},
        {"job_id": "c", "title": "Gamma", "location": "Remote", "score": 70},
    ]
    prev_index = build_last_seen(prev_jobs)
    alerts = compute_alerts(curr_jobs, prev_index, score_delta=10)

    assert alerts["counts"]["new"] == 1
    assert alerts["counts"]["removed"] == 1
    assert alerts["new_jobs"][0]["job_id"] == "c"
    assert "a" in alerts["removed_jobs"]


def test_alerts_score_change_threshold() -> None:
    prev_jobs = [{"job_id": "a", "title": "Alpha", "location": "SF", "score": 50}]
    curr_jobs = [{"job_id": "a", "title": "Alpha", "location": "SF", "score": 65}]
    prev_index = build_last_seen(prev_jobs)
    alerts = compute_alerts(curr_jobs, prev_index, score_delta=10)

    assert alerts["counts"]["score_changes"] == 1
    assert alerts["score_changes"][0]["delta"] == 15


def test_title_location_hash_changes() -> None:
    job = {"job_id": "a", "title": "Alpha", "location": "SF"}
    changed = {"job_id": "a", "title": "Alpha", "location": "NY"}
    assert stable_title_location_hash(job) != stable_title_location_hash(changed)
