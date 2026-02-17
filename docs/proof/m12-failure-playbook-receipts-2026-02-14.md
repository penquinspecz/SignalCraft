# M12: Failure Playbook Receipts (2026-02-14)

## Summary

Operations Hardening Pack v1 receipts strengthened with operator-friendly proof and documentation:

1. **Force-fail demo script** (`scripts/dev/force_fail_demo.sh`)
2. **Failure playbook** (section in `docs/OPS_RUNBOOK.md`)
3. **E2E test** (`test_forced_failure_e2e_artifact_paths`)

## 1. Force-fail demo script

```bash
./scripts/dev/force_fail_demo.sh scrape
# or: ./scripts/dev/force_fail_demo.sh classify
```

- Runs pipeline with `JOBINTEL_FORCE_FAIL_STAGE` set
- Safe offline (snapshot mode, `--offline --no_subprocess`)
- Prints artifact paths (run_health, run_summary, run_report, provider_availability)
- Exits non-zero (expected on forced failure)

### Example output

```
=== Force-fail demo (stage=scrape, offline) ===
STATE_DIR=/tmp/jobintel_force_fail_demo

... (pipeline logs) ...

=== Artifact paths (latest run) ===
run_dir=/tmp/jobintel_force_fail_demo/runs/20260215T171324Z
run_health=/tmp/jobintel_force_fail_demo/runs/20260215T171324Z/run_health.v1.json
run_summary=/tmp/jobintel_force_fail_demo/runs/20260215T171324Z/run_summary.v1.json
run_report=/tmp/jobintel_force_fail_demo/runs/20260215T171324Z/run_report.json
provider_availability=/tmp/jobintel_force_fail_demo/runs/20260215T171324Z/artifacts/provider_availability_v1.json

run_health.failed_stage=scrape
run_health.failure_codes=['AI_DISABLED', 'FORCED_FAILURE', 'SNAPSHOT_FETCH_FAILED']

=== Done (exit_code=1, expected non-zero on forced failure) ===
```

## 2. Failure playbook (OPS_RUNBOOK.md)

Added section "Failure playbook (local / operator)" with:

- How to force fail (`force_fail_demo.sh`)
- How to inspect run artifacts via CLI (`runs list`, `runs show`, `runs artifacts`)
- What to check first: `failed_stage`, `failure_code`
- How `provider_availability` helps differentiate:
  - **Policy block**: `policy_snapshot`, `snapshot_disabled` → config/ops
  - **Network issue**: `unavailable`, `timeout` → infra/connectivity
  - **Config disable**: provider `enabled: false`

## 3. E2E test

`tests/test_run_health_artifact.py::test_forced_failure_e2e_artifact_paths`:

- Simulates forced failure at scrape
- Asserts `run_health.v1.json` exists with `status=failed`, `failed_stage=scrape`, `FORCED_FAILURE` in `failure_codes`
- Asserts `run_summary.v1.json` exists with `status=failed` and `run_health` pointer
- Documents that `provider_availability` is optional on early forced failure (fail-closed)

## 4. Verification

```bash
make format
make lint
make ci-fast
make gate
./scripts/dev/force_fail_demo.sh scrape
```

## Related

- [docs/proof/m12-forced-failure-receipts-2026-02-15.md](m12-forced-failure-receipts-2026-02-15.md) — forced failure behavior
- [docs/OPS_RUNBOOK.md](../OPS_RUNBOOK.md) — failure playbook section
