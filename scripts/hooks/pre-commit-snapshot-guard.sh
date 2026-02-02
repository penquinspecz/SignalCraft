#!/usr/bin/env bash
set -euo pipefail

if [[ "${ALLOW_SNAPSHOT_CHANGES:-0}" == "1" ]]; then
  exit 0
fi

changed=$(git diff --cached --name-only -- 'data/*_snapshots/*' || true)
if [[ -n "$changed" ]]; then
  echo "ERROR: Pinned snapshot fixtures were modified:" >&2
  echo "$changed" >&2
  echo "Set ALLOW_SNAPSHOT_CHANGES=1 if this is an intentional refresh." >&2
  exit 1
fi
