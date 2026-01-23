#!/usr/bin/env bash
set -euo pipefail

BUCKET="${BUCKET:-${JOBINTEL_S3_BUCKET:-}}"
PREFIX="${PREFIX:-${JOBINTEL_S3_PREFIX:-jobintel}}"
PROVIDER="${PROVIDER:-openai}"
PROFILE="${PROFILE:-cs}"
REGION="${REGION:-${AWS_REGION:-us-east-1}}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required" >&2
  exit 2
fi

if [[ -z "${BUCKET}" ]]; then
  echo "BUCKET is required (or set JOBINTEL_S3_BUCKET)." >&2
  exit 2
fi

pretty_json() {
  if command -v jq >/dev/null 2>&1; then
    jq .
  else
    python - <<'PY'
import json
import sys
print(json.dumps(json.load(sys.stdin), indent=2, sort_keys=True))
PY
  fi
}

missing_ptr=0

print_pointer() {
  local uri="$1"
  local label="$2"
  echo "\n${label}: ${uri}"
  if aws s3 ls "${uri}" >/dev/null 2>&1; then
    aws s3 cp "${uri}" - | pretty_json
  else
    echo "(missing)"
    missing_ptr=1
  fi
}

print_pointer "s3://${BUCKET}/${PREFIX}/state/last_success.json" "Global pointer"
print_pointer "s3://${BUCKET}/${PREFIX}/state/${PROVIDER}/${PROFILE}/last_success.json" "Provider pointer"

latest_run_id=$(aws s3api list-objects-v2 \
  --bucket "${BUCKET}" \
  --prefix "${PREFIX}/runs/" \
  --region "${REGION}" \
  --query "Contents[].Key" \
  --output json | \
  python - <<'PY'
import json
import sys
from datetime import datetime

def parse_run_id(key: str) -> str | None:
    marker = "/runs/"
    if marker not in key:
        return None
    rest = key.split(marker, 1)[1]
    run_id = rest.split("/", 1)[0]
    return run_id or None

keys = json.load(sys.stdin) if not sys.stdin.closed else []
run_ids = {parse_run_id(k) for k in keys}
run_ids.discard(None)

candidates = []
for run_id in run_ids:
    try:
        dt = datetime.fromisoformat(run_id.replace("Z", "+00:00"))
        candidates.append((dt, run_id))
    except Exception:
        candidates.append((run_id, run_id))

if not candidates:
    print("", end="")
else:
    candidates.sort()
    print(candidates[-1][1], end="")
PY
)

if [[ -z "${latest_run_id}" ]]; then
  echo "\nLatest run_id: (none)"
  exit 3
fi

echo "\nLatest run_id: ${latest_run_id}"

run_report_uri="s3://${BUCKET}/${PREFIX}/runs/${latest_run_id}/run_report.json"
if ! aws s3 ls "${run_report_uri}" >/dev/null 2>&1; then
  echo "run_report.json missing for latest run: ${run_report_uri}" >&2
  exit 3
fi

run_report=$(aws s3 cp "${run_report_uri}" -)

echo "\nRun report summary:"
python - <<PY
import json
import os

data = json.loads("""${run_report}""")
provider = os.environ.get("PROVIDER", "openai")
profile = os.environ.get("PROFILE", "cs")

print("success:", data.get("success"))
print("baseline_run_id:", data.get("delta_summary", {}).get("baseline_run_id"))
print("baseline_run_path:", data.get("delta_summary", {}).get("baseline_run_path"))

diff_counts = data.get("diff_counts", {})
if isinstance(diff_counts, dict) and profile in diff_counts:
    print("diff_counts[profile]:", diff_counts.get(profile))
else:
    provider_profiles = data.get("providers", {}).get(provider, {}).get("profiles", {})
    print("diff_counts[provider/profile]:", provider_profiles.get(profile, {}).get("diff_counts"))

prov = data.get("provenance_by_provider", {})
meta = prov.get(provider, {})
print("provenance.live_http_status:", meta.get("live_http_status"))
print("provenance.live_status_code:", meta.get("live_status_code"))
print("provenance.scrape_mode:", meta.get("scrape_mode"))
print("provenance.unavailable_reason:", meta.get("unavailable_reason"))
print("provenance.error:", meta.get("error"))
PY

success=$(python - <<PY
import json
print(json.loads("""${run_report}""").get("success"))
PY
)

if [[ "${success}" != "True" && "${success}" != "true" ]]; then
  echo "Latest run is not successful." >&2
  exit 4
fi

if [[ "${missing_ptr}" -ne 0 ]]; then
  echo "One or more baseline pointers are missing." >&2
  exit 5
fi

echo "\nOK: pointers present and latest run successful."
