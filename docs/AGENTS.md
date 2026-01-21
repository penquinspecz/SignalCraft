# JobIntel Engine — Agent Notes

## Principles
- Deterministic outputs > cleverness.
- CI must be offline/deterministic (use committed snapshots).
- Live network scraping is allowed only via explicit commands (e.g., snapshots refresh).

## Repo conventions
- Data fixtures: `data/*_snapshots/index.html`, `data/candidate_profile.json`
- Runtime writes: use JOBINTEL_DATA_DIR and JOBINTEL_STATE_DIR.

## Commands
- Tests: `./.venv/bin/python -m pytest -q`
- Offline run: `python -m src.jobintel.cli run --offline --role cs`
- Refresh snapshots: `python -m src.jobintel.cli snapshots refresh --provider openai`