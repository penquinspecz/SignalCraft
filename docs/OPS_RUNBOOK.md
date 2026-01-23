# Ops Runbook (ECS + S3)

## Happy path
```bash
./scripts/deploy_ecs_rev.sh
TASKDEF_REV=<newrev> bash ./scripts/run_ecs_once.sh
BUCKET=jobintel-prod1 PREFIX=jobintel bash ./scripts/verify_ops.sh
BUCKET=jobintel-prod1 PREFIX=jobintel bash ./scripts/show_run_provenance.sh
./scripts/print_taskdef_env.sh TASKDEF_REV=<newrev>
```
Note: ECS_TASK_ARN is assigned by ECS after run-task; it is not injected as an env override.

## Failure modes
```bash
# Pointers missing or access denied
BUCKET=jobintel-prod1 PREFIX=jobintel bash ./scripts/verify_ops.sh

# Show build provenance from last_success pointer
BUCKET=jobintel-prod1 PREFIX=jobintel bash ./scripts/show_run_provenance.sh

# Inspect task env + image
TASKDEF_REV=<newrev> ./scripts/print_taskdef_env.sh

# Inspect task runtime status
CLUSTER_ARN=<cluster> TASK_ARN=<task> REGION=us-east-1 ./scripts/ecs_verify_task.sh
```
