#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME=${CONTAINER_NAME:-jobintel_smoke}
ARTIFACT_DIR=${SMOKE_ARTIFACTS_DIR:-${ARTIFACT_DIR:-smoke_artifacts}}
IMAGE_TAG=${IMAGE_TAG:-${JOBINTEL_IMAGE_TAG:-jobintel:local}}
SMOKE_SKIP_BUILD=${SMOKE_SKIP_BUILD:-0}
SMOKE_PROVIDERS=${SMOKE_PROVIDERS:-openai}
SMOKE_PROFILES=${SMOKE_PROFILES:-cs}
SMOKE_NO_ENRICH=-e
SMOKE_UPDATE_SNAPSHOTS=${SMOKE_UPDATE_SNAPSHOTS:-0}
SMOKE_MIN_SCORE=${SMOKE_MIN_SCORE:-40}
SMOKE_OUTPUT_DIR=${SMOKE_OUTPUT_DIR:-/app/data/ashby_cache}
PROVIDERS=${PROVIDERS:-$SMOKE_PROVIDERS}
PROFILES=${PROFILES:-$SMOKE_PROFILES}
SMOKE_TAIL_LINES=${SMOKE_TAIL_LINES:-0}
container_created=0
status=1
missing=0
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "${DOCKER_BUILDKIT:-1}" = "0" ]; then
  echo "BuildKit is required (Dockerfile uses RUN --mount=type=cache). Set DOCKER_BUILDKIT=1."
  exit 1
fi

write_exit_code() {
  mkdir -p "$ARTIFACT_DIR"
  echo "$status" > "$ARTIFACT_DIR/exit_code.txt"
}

write_run_report_placeholder() {
  if [ -f "$ARTIFACT_DIR/run_report.json" ]; then
    return
  fi
  cat > "$ARTIFACT_DIR/run_report.json" <<EOF
{
  "run_id": "unknown",
  "status": "failed",
  "success": false,
  "error": "smoke_run_failed_or_missing_report"
}
EOF
}

write_smoke_summary() {
  mkdir -p "$ARTIFACT_DIR"
  local tmp_summary
  tmp_summary="$ARTIFACT_DIR/smoke_summary.json"
  local py
  py="${PYTHON:-python3}"
  local tail_text
  tail_text=""
  if [ -f "$ARTIFACT_DIR/smoke.log" ]; then
    tail_text="$(tail -n 200 "$ARTIFACT_DIR/smoke.log" 2>/dev/null || true)"
  fi

  IFS=',' read -r -a _providers <<< "$PROVIDERS"
  IFS=',' read -r -a _profiles <<< "$PROFILES"
  local missing_list=()
  for provider in "${_providers[@]}"; do
    provider="$(echo "$provider" | xargs)"
    [ -z "$provider" ] && continue
    if [ ! -f "$ARTIFACT_DIR/${provider}_labeled_jobs.json" ]; then
      missing_list+=("${provider}_labeled_jobs.json")
    fi
    for profile in "${_profiles[@]}"; do
      profile="$(echo "$profile" | xargs)"
      [ -z "$profile" ] && continue
      if [ ! -f "$ARTIFACT_DIR/${provider}_ranked_jobs.${profile}.json" ]; then
        missing_list+=("${provider}_ranked_jobs.${profile}.json")
      fi
      if [ ! -f "$ARTIFACT_DIR/${provider}_ranked_jobs.${profile}.csv" ]; then
        missing_list+=("${provider}_ranked_jobs.${profile}.csv")
      fi
    done
  done
  if [ ! -f "$ARTIFACT_DIR/run_report.json" ]; then
    missing_list+=("run_report.json")
  fi

  local missing_json
  missing_json="[]"
  if [ "${#missing_list[@]}" -gt 0 ]; then
    missing_json="$(printf '%s\n' "${missing_list[@]}" | $py - <<'PY'
import json
import sys
items=[line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(items))
PY
)"
  fi

  cat > "$tmp_summary" <<EOF
{
  "status": "$( [ "$status" -eq 0 ] && echo success || echo failed )",
  "exit_code": $status,
  "providers": "$(echo "$PROVIDERS")",
  "profiles": "$(echo "$PROFILES")",
  "missing_artifacts": $missing_json,
  "stdout_tail": $(printf '%s' "$tail_text" | $py - <<'PY'
import json
import sys
print(json.dumps(sys.stdin.read()))
PY
)
}
EOF
}

write_docker_context() {
  mkdir -p "$ARTIFACT_DIR"
  {
    echo "context: $(docker context show 2>/dev/null || echo unknown)"
    echo "host: $(docker context inspect "$(docker context show 2>/dev/null || echo default)" --format '{{json .Endpoints.docker.Host}}' 2>/dev/null || echo unknown)"
    echo "docker version:"
    docker version 2>/dev/null || true
    echo "docker info:"
    docker info 2>/dev/null || true
  } > "$ARTIFACT_DIR/docker_context.txt"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-build)
      SMOKE_SKIP_BUILD=1
      shift
      ;;
    --tail)
      SMOKE_TAIL_LINES="${2:-0}"
      shift 2
      ;;
    --providers)
      PROVIDERS="${2:-}"
      shift 2
      ;;
    --profiles)
      PROFILES="${2:-}"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--skip-build] [--tail <lines>] [--providers <ids>] [--profiles <profiles>]"
      exit 2
      ;;
  esac
done

mkdir -p "$ARTIFACT_DIR"
touch "$ARTIFACT_DIR/smoke.log"

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  write_exit_code
  write_run_report_placeholder
  write_smoke_summary
}
trap cleanup EXIT

echo "==> Image tag: $IMAGE_TAG"
context="$(docker context show 2>/dev/null || echo unknown)"
host="$(docker context inspect "$context" --format '{{json .Endpoints.docker.Host}}' 2>/dev/null || echo unknown)"
echo "==> Config: image=$IMAGE_TAG providers=$PROVIDERS profiles=$PROFILES skip_build=$SMOKE_SKIP_BUILD context=$context host=$host"
write_docker_context

if [ "$SMOKE_SKIP_BUILD" = "1" ]; then
  if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
    echo "Missing image '$IMAGE_TAG'. Build it first (docker build -t $IMAGE_TAG .) or omit --skip-build."
    exit 1
  fi
  echo "==> Using existing image ($IMAGE_TAG)"
else
  if [ "$SMOKE_UPDATE_SNAPSHOTS" = "1" ] && echo "$PROVIDERS" | grep -q "openai"; then
    echo "==> Update OpenAI snapshots (host)"
    python scripts/update_snapshots.py --provider openai
  fi
  echo "==> Build image ($IMAGE_TAG)"
  docker build -t "$IMAGE_TAG" .
fi

echo "==> Preflight image runtime"
preflight_status=1
last_cmd=""
last_output=""
for cmd in "/usr/local/bin/python -V" "/usr/bin/python3 -V" "python3 -V" "python -V"; do
  set +e
  entrypoint="${cmd%% *}"
  args="${cmd#* }"
  last_output="$(docker run --rm --entrypoint "$entrypoint" "$IMAGE_TAG" $args 2>&1)"
  preflight_status=$?
  set -e
  last_cmd="docker run --rm --entrypoint $entrypoint $IMAGE_TAG $args"
  if [ "$preflight_status" -eq 0 ]; then
    break
  fi
done
if [ "$preflight_status" -ne 0 ]; then
  echo "Preflight failed: unable to run python in image '$IMAGE_TAG'."
  echo "Last command: $last_cmd"
  echo "Last error output:"
  echo "$last_output"
  echo "Preflight bypasses the image ENTRYPOINT; failures mean python is missing or"
  echo "the $IMAGE_TAG tag may have been overwritten by a non-jobintel image."
  echo "Rebuild with: make image"
  exit 1
fi

echo "==> Validate baked-in snapshots"
docker run --rm --entrypoint python "$IMAGE_TAG" \
  -m src.jobintel.cli snapshots validate --all --data-dir /app/data

echo "==> Check job detail snapshots (OpenAI)"
set +e
jobs_count="$(docker run --rm --entrypoint sh "$IMAGE_TAG" -c 'ls -1 /app/data/openai_snapshots/jobs/*.html 2>/dev/null | wc -l' 2>/dev/null)"
set -e
if [ -n "$jobs_count" ] && [ "$jobs_count" -gt 0 ]; then
  echo "OpenAI job snapshots present: $jobs_count"
else
  echo "Warning: no OpenAI job snapshots found in /app/data/openai_snapshots/jobs/."
  echo "Generate with: ./scripts/update_snapshots.py --provider openai --out_dir data/openai_snapshots"
  echo "Then rebuild (or set SMOKE_UPDATE_SNAPSHOTS=1 with SMOKE_SKIP_BUILD=0)."
fi

echo "==> Run smoke container ($CONTAINER_NAME)"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

set +e
docker create --name "$CONTAINER_NAME" \
  --env JOBINTEL_OUTPUT_DIR="$SMOKE_OUTPUT_DIR" \
  "$IMAGE_TAG" --providers "$PROVIDERS" --profiles "$PROFILES" --offline --no_post --min_score "$SMOKE_MIN_SCORE" \
  $(if [ "$SMOKE_NO_ENRICH" = "1" ]; then echo "--no_enrich"; fi) >/dev/null
create_status=$?
set -e
if [ "$create_status" -eq 0 ]; then
  container_created=1
  set +e
  docker start -a "$CONTAINER_NAME" 2>&1 | tee -a "$ARTIFACT_DIR/smoke.log"
  status=${PIPESTATUS[0]}
  set -e
else
  echo "Failed to create smoke container (exit_code=$create_status)"
  echo "Failed to create smoke container (exit_code=$create_status)" >> "$ARTIFACT_DIR/smoke.log"
  status=$create_status
fi

if [ "$status" -ne 0 ] && [ "${SMOKE_TAIL_LINES:-0}" -gt 0 ]; then
  echo "Container failed; last ${SMOKE_TAIL_LINES} lines of logs:"
  tail -n "$SMOKE_TAIL_LINES" "$ARTIFACT_DIR/smoke.log" || true
fi

echo "==> Collect outputs"
IFS=',' read -r -a provider_list <<< "$PROVIDERS"
IFS=',' read -r -a profile_list <<< "$PROFILES"

copy_from_container() {
  local src="$1"
  local required="$2"
  if [ "$container_created" -ne 1 ]; then
    echo "Skipping copy (container not created): $src"
    if [ "$required" = "1" ]; then
      missing=1
    fi
    return 1
  fi
  if ! docker cp "$CONTAINER_NAME:$src" "$ARTIFACT_DIR/$(basename "$src")" 2>/dev/null; then
    if [ "$required" = "1" ]; then
      echo "Missing output: $src"
      missing=1
    else
      echo "Missing optional output: $src"
    fi
    return 1
  fi
  return 0
}

copy_from_container_any() {
  local required="$1"
  shift
  local src
  local copied=0
  for src in "$@"; do
    if copy_from_container "$src" 0; then
      copied=1
      break
    fi
  done
  if [ "$copied" -ne 1 ] && [ "$required" = "1" ]; then
    missing=1
  fi
}

for provider in "${provider_list[@]}"; do
  provider_trimmed="$(echo "$provider" | xargs)"
  if [ -z "$provider_trimmed" ]; then
    continue
  fi
  copy_from_container_any 0 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_raw_jobs.json" "/app/data/${provider_trimmed}_raw_jobs.json"
  copy_from_container_any 1 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_labeled_jobs.json" "/app/data/${provider_trimmed}_labeled_jobs.json"
  copy_from_container_any 0 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_enriched_jobs.json" "/app/data/${provider_trimmed}_enriched_jobs.json"
  for profile in "${profile_list[@]}"; do
    profile_trimmed="$(echo "$profile" | xargs)"
    if [ -z "$profile_trimmed" ]; then
      continue
    fi
    copy_from_container_any 1 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_ranked_jobs.${profile_trimmed}.json" "/app/data/${provider_trimmed}_ranked_jobs.${profile_trimmed}.json" "/app/data/${provider_trimmed}/${profile_trimmed}/${provider_trimmed}_ranked_jobs.${profile_trimmed}.json"
    copy_from_container_any 1 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_ranked_jobs.${profile_trimmed}.csv" "/app/data/${provider_trimmed}_ranked_jobs.${profile_trimmed}.csv" "/app/data/${provider_trimmed}/${profile_trimmed}/${provider_trimmed}_ranked_jobs.${profile_trimmed}.csv"
    copy_from_container_any 0 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_shortlist.${profile_trimmed}.md" "/app/data/${provider_trimmed}_shortlist.${profile_trimmed}.md" "/app/data/${provider_trimmed}/${profile_trimmed}/${provider_trimmed}_shortlist.${profile_trimmed}.md"
    copy_from_container_any 0 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_top.${profile_trimmed}.md" "/app/data/${provider_trimmed}_top.${profile_trimmed}.md" "/app/data/${provider_trimmed}/${profile_trimmed}/${provider_trimmed}_top.${profile_trimmed}.md"
    copy_from_container_any 0 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_ranked_families.${profile_trimmed}.json" "/app/data/${provider_trimmed}_ranked_families.${profile_trimmed}.json" "/app/data/${provider_trimmed}/${profile_trimmed}/${provider_trimmed}_ranked_families.${profile_trimmed}.json"
    copy_from_container_any 0 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_alerts.${profile_trimmed}.json" "/app/data/${provider_trimmed}_alerts.${profile_trimmed}.json" "/app/data/${provider_trimmed}/${profile_trimmed}/${provider_trimmed}_alerts.${profile_trimmed}.json"
    copy_from_container_any 0 "$SMOKE_OUTPUT_DIR/${provider_trimmed}_alerts.${profile_trimmed}.md" "/app/data/${provider_trimmed}_alerts.${profile_trimmed}.md" "/app/data/${provider_trimmed}/${profile_trimmed}/${provider_trimmed}_alerts.${profile_trimmed}.md"
  done
done

rm -rf "$ARTIFACT_DIR/state_runs"
if [ "$container_created" -eq 1 ] && docker cp "$CONTAINER_NAME:/app/state/runs" "$ARTIFACT_DIR/state_runs" 2>/dev/null; then
  run_report="$(ls -1 "$ARTIFACT_DIR"/state_runs/*.json 2>/dev/null | sort | tail -n 1)"
  if [ -n "$run_report" ]; then
    cp "$run_report" "$ARTIFACT_DIR/run_report.json" 2>/dev/null || true
  fi
fi

if [ "$missing" -ne 0 ]; then
  echo "Available /app/data contents:"
  if [ "$container_created" -eq 1 ]; then
    docker cp "$CONTAINER_NAME:/app/data" "$ARTIFACT_DIR/data" 2>/dev/null || true
    ls -la "$ARTIFACT_DIR/data" 2>/dev/null || true
  fi
fi

PYTHON=${PYTHON:-python3}
echo "==> Write metadata"
PYTHONPATH="$repo_root/src" $PYTHON -m scripts.smoke_metadata --out "$ARTIFACT_DIR/metadata.json" --providers "$PROVIDERS" --profiles "$PROFILES"

echo "==> Verify artifact presence"
ls -la "$ARTIFACT_DIR" || true

echo "==> Smoke contract check"
PYTHONPATH="$repo_root/src" $PYTHON scripts/smoke_contract_check.py "$ARTIFACT_DIR" --providers "$PROVIDERS" --profiles "$PROFILES"

if [ "$status" -ne 0 ] || [ "$missing" -ne 0 ]; then
  echo "Smoke failed (exit_code=$status, missing_outputs=$missing)"
  exit 1
fi

echo "Smoke succeeded. Artifacts in $ARTIFACT_DIR"
