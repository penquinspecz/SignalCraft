#!/usr/bin/env bash
# List merged PRs labeled from-composer since a given date or commit.
# Usage: ./scripts/dev/list_from_composer_prs.sh [--since-date YYYY-MM-DD] [--since-commit SHA] [--limit N]
# Default: --since-date 7 days ago

set -euo pipefail

SINCE_DATE=""
SINCE_COMMIT=""
LIMIT=50

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since-date)
      SINCE_DATE="$2"
      shift 2
      ;;
    --since-commit)
      SINCE_COMMIT="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$SINCE_DATE" && -z "$SINCE_COMMIT" ]]; then
  if date -u -v-7d +%Y-%m-%d 2>/dev/null; then
    SINCE_DATE=$(date -u -v-7d +%Y-%m-%d)
  else
    SINCE_DATE=$(date -u -d "7 days ago" +%Y-%m-%d)
  fi
fi

if [[ -n "$SINCE_COMMIT" ]]; then
  SINCE_DATE=$(git log -1 --format=%cI "$SINCE_COMMIT" 2>/dev/null | cut -d'T' -f1 || true)
  if [[ -z "$SINCE_DATE" ]]; then
    echo "Invalid --since-commit: $SINCE_COMMIT" >&2
    exit 2
  fi
fi

command -v jq >/dev/null 2>&1 || {
  echo "jq is required. Install via: brew install jq" >&2
  exit 2
}

command -v gh >/dev/null 2>&1 || {
  echo "gh CLI is required. Install via: brew install gh" >&2
  exit 2
}

json=$(gh pr list --state merged --label "from-composer" --limit "$LIMIT" \
  --json number,title,mergedAt,headRefName,mergeCommit,url 2>/dev/null)

if [[ -z "$json" || "$json" == "[]" ]]; then
  echo "No merged from-composer PRs found."
  exit 0
fi

filtered=$(echo "$json" | jq --arg since "${SINCE_DATE}T00:00:00Z" '
  [.[] | select(.mergedAt >= $since)]
')

if [[ -z "$filtered" || "$filtered" == "[]" ]]; then
  echo "No merged from-composer PRs in range (since: $SINCE_DATE)."
  exit 0
fi

echo "$filtered" | jq -r '.[] | @base64' | while read -r b64; do
  pr=$(echo "$b64" | base64 -d 2>/dev/null || echo "$b64" | base64 -D 2>/dev/null)
  num=$(echo "$pr" | jq -r '.number')
  title=$(echo "$pr" | jq -r '.title')
  merged=$(echo "$pr" | jq -r '.mergedAt')
  branch=$(echo "$pr" | jq -r '.headRefName')
  sha=$(echo "$pr" | jq -r '.mergeCommit.oid')
  url=$(echo "$pr" | jq -r '.url')

  if [[ -n "$SINCE_DATE" && "$merged" < "${SINCE_DATE}T00:00:00Z" ]]; then
    continue
  fi

  files=""
  if gh pr view "$num" --json files 2>/dev/null | jq -e '.files' >/dev/null 2>&1; then
    files=$(gh pr view "$num" --json files --jq '.files[].path' 2>/dev/null | head -20 | tr '\n' ' ')
  fi

  echo "---"
  echo "PR #$num: $title"
  echo "  Merge: $sha"
  echo "  Branch: $branch"
  echo "  Merged: $merged"
  echo "  URL: $url"
  echo "  Files: $files"
  echo ""
done
