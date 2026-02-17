#!/usr/bin/env bash
# Generate Codex review queue markdown for merged from-composer PRs.
# Usage: ./scripts/dev/generate_codex_review_queue.sh [--since-date YYYY-MM-DD] [--since-commit SHA] [--limit N]
# Writes: docs/proof/from-composer-codex-review-queue-YYYY-MM-DD.md
# Ordering: mergedAt ascending (deterministic)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

SINCE_DATE=""
SINCE_COMMIT=""
LIMIT=""
USER_LIMIT_SET=false
INTERNAL_FETCH_CAP="${FROM_COMPOSER_INTERNAL_CAP:-5000}"

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
      USER_LIMIT_SET=true
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "$LIMIT" ]] && ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
  echo "Invalid --limit value: $LIMIT" >&2
  exit 2
fi
if [[ -n "$LIMIT" && "$LIMIT" -le 0 ]]; then
  echo "--limit must be > 0" >&2
  exit 2
fi
if ! [[ "$INTERNAL_FETCH_CAP" =~ ^[0-9]+$ ]] || [[ "$INTERNAL_FETCH_CAP" -le 0 ]]; then
  echo "Invalid FROM_COMPOSER_INTERNAL_CAP: $INTERNAL_FETCH_CAP" >&2
  exit 2
fi

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

OUTPUT_FILE="${FROM_COMPOSER_OUTPUT_FILE:-docs/proof/from-composer-codex-review-queue-$(date -u +%Y-%m-%d).md}"

origin_url="$(git config --get remote.origin.url || true)"
if [[ -z "$origin_url" ]]; then
  echo "Unable to resolve repository from git remote.origin.url" >&2
  exit 2
fi
origin_url="${origin_url%.git}"
if [[ "$origin_url" =~ github\.com[:/]([^/]+)/([^/]+)$ ]]; then
  owner="${BASH_REMATCH[1]}"
  repo="${BASH_REMATCH[2]}"
else
  echo "Unsupported GitHub remote URL: $origin_url" >&2
  exit 2
fi

query='
query($owner: String!, $repo: String!, $endCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequests(
      first: 100
      after: $endCursor
      states: MERGED
      labels: ["from-composer"]
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      nodes {
        number
        title
        mergedAt
        headRefName
        url
        mergeCommit {
          oid
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
'

cursor=""
all_nodes='[]'
total_discovered=0
internal_truncated=false

while :; do
  if [[ -n "$cursor" ]]; then
    page="$(gh api graphql -f query="$query" -F owner="$owner" -F repo="$repo" -F endCursor="$cursor" 2>/dev/null)"
  else
    page="$(gh api graphql -f query="$query" -F owner="$owner" -F repo="$repo" 2>/dev/null)"
  fi
  nodes="$(echo "$page" | jq -c '.data.repository.pullRequests.nodes // []')"
  page_count="$(echo "$nodes" | jq 'length')"
  total_discovered=$((total_discovered + page_count))
  all_nodes="$(jq -c --argjson acc "$all_nodes" --argjson nodes "$nodes" '$acc + $nodes' <<< 'null')"
  has_next="$(echo "$page" | jq -r '.data.repository.pullRequests.pageInfo.hasNextPage // false')"
  if [[ "$has_next" != "true" ]]; then
    break
  fi
  if [[ "$total_discovered" -ge "$INTERNAL_FETCH_CAP" ]]; then
    internal_truncated=true
    break
  fi
  cursor="$(echo "$page" | jq -r '.data.repository.pullRequests.pageInfo.endCursor // ""')"
  if [[ -z "$cursor" ]]; then
    break
  fi
done

if [[ "$internal_truncated" == "true" && "$USER_LIMIT_SET" == "false" ]]; then
  echo "Completeness assertion failed: internal cap reached (${INTERNAL_FETCH_CAP}) without --limit." >&2
  echo "Re-run with FROM_COMPOSER_INTERNAL_CAP increased or pass --limit intentionally." >&2
  exit 1
fi

filtered="$(echo "$all_nodes" | jq -c --arg since "${SINCE_DATE}T00:00:00Z" '
  [.[] | select((.mergedAt // "") >= $since)] | sort_by(.mergedAt, .number)
')"
total_in_range="$(echo "$filtered" | jq 'length')"

if [[ "$USER_LIMIT_SET" == "true" ]]; then
  included="$(echo "$filtered" | jq -c --argjson limit "$LIMIT" '.[0:$limit]')"
  total_included="$(echo "$included" | jq 'length')"
  if [[ "$total_in_range" -gt "$LIMIT" ]] || [[ "$internal_truncated" == "true" ]]; then
    truncated="true"
  else
    truncated="false"
  fi
else
  included="$filtered"
  total_included="$total_in_range"
  truncated="false"
fi

if [[ "$total_included" -eq 0 ]]; then
  echo "No merged from-composer PRs in range. Writing empty queue."
  mkdir -p "$(dirname "$OUTPUT_FILE")"
  cat > "$OUTPUT_FILE" << EOF
# From-Composer Codex Review Queue ($(date -u +%Y-%m-%d))

Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

## Scope

Since: $SINCE_DATE
Ordering: mergedAt ascending

## Metadata

- total_discovered: $total_discovered
- total_in_range: $total_in_range
- total_included: $total_included
- truncated: false

## PRs

No PRs in range.
EOF
  echo "Wrote: $OUTPUT_FILE"
  exit 0
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

{
  echo "# From-Composer Codex Review Queue ($(date -u +%Y-%m-%d))"
  echo ""
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  echo "## Scope"
  echo ""
  echo "Since: $SINCE_DATE"
  echo "Ordering: mergedAt ascending"
  echo ""
  echo "## Metadata"
  echo ""
  echo "- total_discovered: $total_discovered"
  echo "- total_in_range: $total_in_range"
  echo "- total_included: $total_included"
  echo "- truncated: $truncated"
  echo ""
  echo "## PRs"
  echo ""

  echo "$included" | jq -r '.[] | @base64' | while read -r b64; do
    pr=$(echo "$b64" | base64 -d 2>/dev/null || echo "$b64" | base64 -D 2>/dev/null)
    num=$(echo "$pr" | jq -r '.number')
    title=$(echo "$pr" | jq -r '.title')
    sha=$(echo "$pr" | jq -r '.mergeCommit.oid')
    url=$(echo "$pr" | jq -r '.url')

    echo "### PR #$num: $title"
    echo ""
    echo "- **URL:** $url"
    echo "- **Merge SHA:** \`$sha\`"
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
