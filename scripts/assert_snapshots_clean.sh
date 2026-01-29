#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
changed="$(git -C "$repo_root" diff --name-only -- data/*_snapshots 2>/dev/null || true)"
if [ -n "$changed" ]; then
  echo "ERROR: Snapshot fixtures were modified during tests."
  echo "Do not mutate committed fixtures under data/*_snapshots."
  echo "To update snapshots, use the explicit snapshot-update workflow."
  echo ""
  echo "Changed files:"
  echo "$changed"
  exit 1
fi
