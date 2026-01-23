#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   LOG_GROUP=/ecs/jobintel REGION=us-east-1 LOOKBACK_MINUTES=60 FILTER=baseline ./scripts/cw_tail.sh
#   ./scripts/cw_tail.sh --log-group /ecs/jobintel --region us-east-1 --lookback 30 --filter "last_success"
#
# Safe filters (avoid slashes): baseline | last_success | publish | availability | ProviderFetchError

LOG_GROUP="${LOG_GROUP:-/ecs/jobintel}"
REGION="${REGION:-${AWS_REGION:-us-east-1}}"
LOOKBACK_MINUTES="${LOOKBACK_MINUTES:-60}"
FILTER="${FILTER:-}"
ORDER="${ORDER:-newest}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --log-group) LOG_GROUP="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --lookback) LOOKBACK_MINUTES="$2"; shift 2 ;;
    --filter) FILTER="$2"; shift 2 ;;
    --order) ORDER="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
 done

start_time=$((($(date +%s)-LOOKBACK_MINUTES*60)*1000))

args=(--log-group-name "${LOG_GROUP}" --start-time "${start_time}" --region "${REGION}")
if [[ -n "${FILTER}" ]]; then
  args+=(--filter-pattern "${FILTER}")
fi

if [[ "${ORDER}" == "newest" ]]; then
  aws logs filter-log-events "${args[@]}" --query 'events | reverse(@)' --output text
else
  aws logs filter-log-events "${args[@]}" --query 'events' --output text
fi
