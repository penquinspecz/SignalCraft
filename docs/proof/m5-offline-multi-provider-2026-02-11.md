# Milestone 5 Offline Multi-Provider Proof Receipt

- run_id: `m5-proof-2026-02-11T23:59:15Z`
- run_artifacts: `state/runs/m5proof20260211T235915Z/`
- run_report: `state/runs/m5proof20260211T235915Z/run_report.json`

## Commands
```bash
JOBINTEL_RUN_ID='m5-proof-2026-02-11T23:59:15Z' AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true ./.venv/bin/python scripts/run_daily.py --providers openai,scaleai,replit --providers-config config/providers.json --profiles cs --offline --snapshot-only --no_post --no_enrich
```

## Provider provenance (from run_report.json)
- openai: extraction_mode=`ashby`, availability=`available`, scrape_mode=`snapshot`, parsed_job_count=`493`, snapshot_path=`data/openai_snapshots/index.html`
- scaleai: extraction_mode=`ashby`, availability=`available`, scrape_mode=`snapshot`, parsed_job_count=`2`, snapshot_path=`data/scaleai_snapshots/index.html`
- replit: extraction_mode=`ashby`, availability=`available`, scrape_mode=`snapshot`, parsed_job_count=`2`, snapshot_path=`data/replit_snapshots/index.html`

## Ranked outputs (profile `cs`)
- `data/ashby_cache/openai_ranked_jobs.cs.json`
- `data/ashby_cache/scaleai_ranked_jobs.cs.json`
- `data/ashby_cache/replit_ranked_jobs.cs.json`
