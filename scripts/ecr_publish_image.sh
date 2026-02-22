#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Backward-compatible wrapper. Prefer scripts/release/build_and_push_ecr.sh directly.
exec "${ROOT_DIR}/scripts/release/build_and_push_ecr.sh" "$@"
