#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

snapshot_path="data/openai_snapshots/index.html"

host_sha=$(python - <<'PY'
import hashlib
from pathlib import Path
p = Path("data/openai_snapshots/index.html")
print(hashlib.sha256(p.read_bytes()).hexdigest())
PY
)
host_bytes=$(python - <<'PY'
from pathlib import Path
p = Path("data/openai_snapshots/index.html")
print(p.stat().st_size)
PY
)

printf "host:   sha256=%s bytes=%s\n" "$host_sha" "$host_bytes"

container_out=$(docker run --rm -v "$repo_root":/app -w /app python:3.12-slim python - <<'PY'
import hashlib
from pathlib import Path
p = Path("data/openai_snapshots/index.html")
print(hashlib.sha256(p.read_bytes()).hexdigest())
print(p.stat().st_size)
PY
)
container_sha=$(printf "%s" "$container_out" | sed -n '1p')
container_bytes=$(printf "%s" "$container_out" | sed -n '2p')

printf "docker: sha256=%s bytes=%s\n" "$container_sha" "$container_bytes"

build_log="$(mktemp)"
trap 'rm -f "$build_log"' EXIT
if ! docker build --no-cache --build-arg RUN_TESTS=1 --build-arg PRINT_SNAPSHOT_SHA=1 -t jobintel:tests . | tee "$build_log"; then
  echo "ERROR: docker build failed; cannot verify build snapshot bytes." >&2
  exit 2
fi

build_sha=$(awk '/sha256sum \/app\/data\/openai_snapshots\/index.html/ {print $NF}' "$build_log" | tail -n 1)
build_bytes=$(awk '/wc -c \/app\/data\/openai_snapshots\/index.html/ {print $NF}' "$build_log" | tail -n 1)

if [[ -z "$build_sha" || -z "$build_bytes" ]]; then
  echo "ERROR: could not find snapshot sha/bytes in docker build output." >&2
  exit 2
fi

printf "build:  sha256=%s bytes=%s\n" "$build_sha" "$build_bytes"

if [[ "$host_sha" != "$container_sha" || "$host_bytes" != "$container_bytes" || "$host_sha" != "$build_sha" || "$host_bytes" != "$build_bytes" ]]; then
  echo "ERROR: snapshot bytes differ across environments." >&2
  exit 1
fi
