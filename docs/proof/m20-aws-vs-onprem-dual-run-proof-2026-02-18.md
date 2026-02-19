# M20 AWS vs On-Prem Dual-Run Proof - 2026-02-18

## Objective
Make AWS execution emit the same required baseline artifacts as on-prem, then run `scripts/compare_run_artifacts.py` on a real AWS/on-prem pair until PASS.

## Environment
- Repo: `/Users/chris.menendez/Projects/signalcraft`
- AWS context: `arn:aws:eks:us-east-1:048622080012:cluster/jobintel-eks`
- Candidate: `local`
- Providers: `openai`
- Profile: `cs`
- Mode: `--snapshot-only --offline`

## AWS Entrypoint + Deployed Image (Evidence)
Entrypoint in live CronJob:
```bash
kubectl --context arn:aws:eks:us-east-1:048622080012:cluster/jobintel-eks -n jobintel \
  get cronjob jobintel-daily -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[0].command}{" "}{.spec.jobTemplate.spec.template.spec.containers[0].args}{"\n"}'
```

Live image before fix:
```bash
kubectl --context arn:aws:eks:us-east-1:048622080012:cluster/jobintel-eks -n jobintel \
  get cronjob jobintel-daily -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[0].image}{"\n"}'
# 048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel:live-snapshotdir-20260205-082950
```

## Before Fix: Missing Baseline Artifacts on AWS
Old-image probe run (same provider/profile/mode) produced ranked outputs but not v1 run artifacts.

Required baseline presence comparison:

| artifact | old aws image live-snapshotdir-20260205-082950 | new aws image ea2dcb6 | on-prem |
|---|---|---|---|
| `run_summary.v1.json` | no | yes | yes |
| `run_health.v1.json` | no | yes | yes |
| `artifacts/provider_availability_v1.json` | no | yes | yes |
| `openai/cs/*ranked_jobs*.json` | yes | yes | yes |
| `openai/cs/*ranked_jobs*.csv` | yes | yes | yes |
| `openai/cs/*ranked_families*.json` | yes | yes | yes |

Old-image file evidence (`find /app/state -type f | sort` excerpt):
- present: `/app/state/runs/20260218T032512304462+0000/run_report.json`
- present: `/app/state/runs/20260218T032512304462+0000/openai/cs/openai_ranked_jobs.cs.json`
- absent: `run_summary.v1.json`, `run_health.v1.json`, `artifacts/provider_availability_v1.json`

## Fix Applied (Smallest First)
1. Published current-main image from `ea2dcb6` to ECR and ensured `linux/amd64` manifest:
```bash
AWS_PROFILE=jobintel-deployer AWS_REGION=us-east-1 ECR_REPO=jobintel scripts/ecr_publish_image.sh
# IMAGE_URI=048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel:ea2dcb6

docker buildx build --platform linux/amd64 \
  -t 048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel:ea2dcb6 --push .

docker buildx imagetools inspect 048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel:ea2dcb6
# Platform: linux/amd64
```
2. Updated live EKS CronJob to that image:
```bash
kubectl --context arn:aws:eks:us-east-1:048622080012:cluster/jobintel-eks -n jobintel \
  set image cronjob/jobintel-daily jobintel=048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel:ea2dcb6
```
3. Synced repo manifests to the same tag:
- `ops/k8s/jobintel/cronjob.yaml`
- `ops/k8s/jobintel/jobs/jobintel-liveproof.job.yaml`
- `ops/k8s/jobintel/jobs/jobintel-politeness-proof.job.yaml`
4. Comparator normalization hardening for real cross-environment runs:
- `scripts/compare_run_artifacts.py`
- `tests/test_compare_run_artifacts.py`

Why comparator hardening was required:
- `run_health.phases.*.duration_sec` differs across environments.
- `run_summary.primary_artifacts[*].sha256` can differ when hashes include volatile metadata.
- Those fields are environment-variant metadata, not score/order/schema drift.

## Real Pair Executed
### AWS run
- Job: `m20-aws-proof-hold-20260218031538`
- Pod: `m20-aws-proof-hold-20260218031538-qv9bk`
- Run ID: `2026-02-18T03:15:40Z`
- Copied artifact root: `/tmp/m20-current-aws/run`

### On-prem run
- Command:
```bash
PYTHONPATH=src JOBINTEL_DATA_DIR=/tmp/m20-current-onprem/data JOBINTEL_STATE_DIR=/tmp/m20-current-onprem/state \
  ./.venv/bin/python scripts/run_daily.py --profiles cs --providers openai --us_only --no_post --snapshot-only --offline
```
- Run ID: `2026-02-18T03:19:05Z`
- Artifact root: `/tmp/m20-current-onprem/state/runs/20260218T031905Z`

## Comparator Command + Result
Command:
```bash
PYTHONPATH=. ./.venv/bin/python scripts/compare_run_artifacts.py \
  --allow-run-id-drift \
  /tmp/m20-current-aws/run \
  /tmp/m20-current-onprem/state/runs/20260218T031905Z
```

Output:
```text
PASS: dual-run deterministic comparison matched
left_run_dir=/private/tmp/m20-current-aws/run
right_run_dir=/private/tmp/m20-current-onprem/state/runs/20260218T031905Z
allow_run_id_drift=True
```

## Validation Commands
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest -q tests/test_compare_run_artifacts.py
# 4 passed
```

## Conclusion
- AWS now emits the same required baseline artifacts as on-prem for this contract.
- Real AWS vs on-prem dual-run comparator now PASSes with `--allow-run-id-drift`.
