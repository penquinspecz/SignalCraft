#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-jobintel}"
RUN_JOB="${RUN_JOB:-0}"

command -v kubectl >/dev/null || { echo "kubectl is required" >&2; exit 2; }

kubectl get ns "${NAMESPACE}" >/dev/null
kubectl -n "${NAMESPACE}" get cronjob jobintel-daily
kubectl -n "${NAMESPACE}" get deploy jobintel-dashboard
kubectl -n "${NAMESPACE}" get pods -o wide

if [[ "${RUN_JOB}" == "1" ]]; then
  job="jobintel-dr-validate-$(date +%Y%m%d%H%M%S)"
  kubectl -n "${NAMESPACE}" create job --from=cronjob/jobintel-daily "${job}"
  kubectl -n "${NAMESPACE}" wait --for=condition=complete --timeout=45m "job/${job}"
  kubectl -n "${NAMESPACE}" logs "job/${job}" | tail -n 200
fi

echo "dr validate checks completed"
