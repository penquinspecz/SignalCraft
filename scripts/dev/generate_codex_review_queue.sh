#!/usr/bin/env bash
# Generate Codex review queue markdown for merged from-composer PRs.
# Usage: ./scripts/dev/generate_codex_review_queue.sh [--since-date YYYY-MM-DD] [--since-commit SHA] [--limit N]
# Writes: docs/proof/from-composer-codex-review-queue-YYYY-MM-DD.md

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

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

OUTPUT_FILE="docs/proof/from-composer-codex-review-queue-$(date -u +%Y-%m-%d).md"

json=$(gh pr list --state merged --label "from-composer" --limit "$LIMIT" \
  --json number,title,mergedAt,headRefName,mergeCommit,url,body 2>/dev/null)

filtered=$(echo "$json" | jq --arg since "${SINCE_DATE}T00:00:00Z" '
  [.[] | select(.mergedAt >= $since)] | sort_by(.mergedAt) | reverse
')

if [[ -z "$filtered" || "$filtered" == "[]" ]]; then
  echo "No merged from-composer PRs in range. Writing empty queue."
  mkdir -p docs/proof
  cat > "$OUTPUT_FILE" << EOF
# From-Composer Codex Review Queue ($(date -u +%Y-%m-%d))

Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

## Scope

Since: $SINCE_DATE

## PRs

No PRs in range.
EOF
  echo "Wrote: $OUTPUT_FILE"
  exit 0
fi

mkdir -p docs/proof

{
  echo "# From-Composer Codex Review Queue ($(date -u +%Y-%m-%d))"
  echo ""
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  echo "## Scope"
  echo ""
  echo "Since: $SINCE_DATE"
  echo ""
  echo "## PRs"
  echo ""

  echo "$filtered" | jq -r '.[] | @base64' | while read -r b64; do
    pr=$(echo "$b64" | base64 -d 2>/dev/null || echo "$b64" | base64 -D 2>/dev/null)
    num=$(echo "$pr" | jq -r '.number')
    title=$(echo "$pr" | jq -r '.title')
    sha=$(echo "$pr" | jq -r '.mergeCommit.oid')
    url=$(echo "$pr" | jq -r '.url')

    files=""
    if gh pr view "$num" --json files 2>/dev/null | jq -e '.files' >/dev/null 2>&1; then
      files=$(gh pr view "$num" --json files --jq '.files[].path' 2>/dev/null | sed 's/^/- /' | tr '\n' '\n')
    fi

    echo "### PR #$num: $title"
    echo ""
    echo "- **URL:** $url"
    echo "- **Merge SHA:** \`$sha\`"
    echo "- **Files changed:**"
    echo "$files" | while read -r line; do [[ -n "$line" ]] && echo "  $line"; done
    echo ""
    echo "<details>"
    echo "<summary>Codex review prompt (paste-ready)</summary>"
    echo ""
    echo '```'
    echo "Review merged PR #$num ($title) for:"
    echo ""
    echo "1. Determinism: Do changes preserve replay determinism? Any new non-deterministic paths?"
    echo "2. Security: Any new filesystem/network exposure? Input validation gaps?"
    echo "3. Replay: Do artifact schemas or run metadata contracts remain backward-compatible?"
    echo "4. Regression: Could these changes break existing tests or gate conditions?"
    echo ""
    echo "PR: $url"
    echo "Merge: $sha"
    echo '```'
    echo ""
    echo "</details>"
    echo ""
  done
} > "$OUTPUT_FILE"

echo "Wrote: $OUTPUT_FILE"
