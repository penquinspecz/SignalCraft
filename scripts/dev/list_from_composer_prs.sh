#!/usr/bin/env bash
# List merged PRs labeled from-composer since a given date or commit.
# Usage: ./scripts/dev/list_from_composer_prs.sh [--since-date YYYY-MM-DD] [--since-commit SHA] [--limit N]
# Default: --since-date 7 days ago
# Ordering: mergedAt ascending (deterministic)

set -euo pipefail

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

if [[ -n "$LIMIT" ]] && ! [[ "$LIMIT" =~ ^[0-9]+$ ]] ; then
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

echo "metadata.since_date: $SINCE_DATE"
echo "metadata.ordering: mergedAt_asc"
echo "metadata.total_discovered: $total_discovered"
echo "metadata.total_in_range: $total_in_range"
echo "metadata.total_included: $total_included"
echo "metadata.truncated: $truncated"

if [[ "$total_included" -eq 0 ]]; then
  exit 0
fi

echo "$included" | jq -r '.[] | @base64' | while read -r b64; do
  pr="$(echo "$b64" | base64 -d 2>/dev/null || echo "$b64" | base64 -D 2>/dev/null)"
  num="$(echo "$pr" | jq -r '.number')"
  title="$(echo "$pr" | jq -r '.title')"
  merged="$(echo "$pr" | jq -r '.mergedAt')"
  branch="$(echo "$pr" | jq -r '.headRefName')"
  sha="$(echo "$pr" | jq -r '.mergeCommit.oid // ""')"
  url="$(echo "$pr" | jq -r '.url')"
  echo "---"
  echo "PR #$num: $title"
  echo "  Merge: $sha"
  echo "  Branch: $branch"
  echo "  Merged: $merged"
  echo "  URL: $url"
done
