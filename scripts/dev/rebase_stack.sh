#!/usr/bin/env bash
set -euo pipefail

# Rebase stacked PR branches onto origin/main in a safe, reviewable flow.
# - Never force-pushes automatically.
# - Stops on conflicts or CI failures.
# - Prints exact push commands for manual execution.

STACK_BRANCHES=(
  "codex/docs-roadmap-security-indexing-dod"
  "codex/sec-network-shield-v1"
  "codex/refactor-pipeline-stages"
  "codex/feat-run-index-readpath"
  "codex/arch-pipeline-seam-hardening"
  "codex/sec-network-egress-audit-v1"
)

usage() {
  cat <<'EOF'
Usage:
  scripts/dev/rebase_stack.sh [--yes] [--skip-ci]

Options:
  --yes      Non-interactive mode (skip confirmation prompt).
  --skip-ci  Skip `make ci-fast` after each branch rebase.
  -h, --help Show this help.
EOF
}

log() {
  printf '[rebase-stack] %s\n' "$*"
}

die() {
  printf '[rebase-stack][ERROR] %s\n' "$*" >&2
  exit 1
}

confirm() {
  local prompt="$1"
  local reply
  printf '%s [y/N]: ' "$prompt"
  read -r reply
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

must_be_git_repo() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "Not inside a git repository."
}

must_be_clean_worktree() {
  if [[ -n "$(git status --porcelain)" ]]; then
    die "Working tree is not clean. Commit/stash changes before rebasing."
  fi
}

ensure_local_branch() {
  local branch="$1"
  if git show-ref --verify --quiet "refs/heads/$branch"; then
    return 0
  fi
  if git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    log "Creating local branch '$branch' tracking 'origin/$branch'."
    git checkout -b "$branch" --track "origin/$branch"
    return 0
  fi
  die "Branch '$branch' not found locally or on origin."
}

parse_args() {
  ASSUME_YES=0
  SKIP_CI=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --yes)
        ASSUME_YES=1
        shift
        ;;
      --skip-ci)
        SKIP_CI=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown argument: $1"
        ;;
    esac
  done
}

main() {
  parse_args "$@"
  must_be_git_repo
  must_be_clean_worktree

  local start_branch
  start_branch="$(git rev-parse --abbrev-ref HEAD)"
  local rebased=()
  local failed_branch=""
  local in_progress=""

  log "Branch order:"
  local b
  for b in "${STACK_BRANCHES[@]}"; do
    printf '  - %s\n' "$b"
  done

  if [[ "$ASSUME_YES" -ne 1 ]]; then
    confirm "Proceed with fetch + main sync + rebase sequence?" || die "Cancelled."
  fi

  log "Fetching remotes..."
  git fetch --all --prune

  log "Updating local main from origin/main..."
  git checkout main
  git pull --ff-only origin main

  for b in "${STACK_BRANCHES[@]}"; do
    ensure_local_branch "$b"

    log "Rebasing '$b' onto origin/main..."
    git checkout "$b"
    in_progress="$b"
    if ! git rebase origin/main; then
      failed_branch="$b"
      printf '\n'
      log "Conflict encountered on '$b'."
      log "Resolve conflicts, then run: git rebase --continue"
      log "Or abort with: git rebase --abort"
      break
    fi
    in_progress=""

    if [[ "$SKIP_CI" -ne 1 ]]; then
      log "Running make ci-fast on '$b'..."
      if ! make ci-fast; then
        failed_branch="$b"
        printf '\n'
        log "ci-fast failed on '$b'."
        log "Fix issues on this branch, then rerun script from a clean worktree."
        break
      fi
    fi

    rebased+=("$b")
  done

  log "Restoring starting branch '$start_branch'..."
  git checkout "$start_branch"

  printf '\n'
  log "===== Summary ====="
  if [[ "${#rebased[@]}" -gt 0 ]]; then
    log "Successfully rebased:"
    for b in "${rebased[@]}"; do
      printf '  - %s\n' "$b"
    done
  else
    log "No branches rebased."
  fi

  if [[ -n "$failed_branch" ]]; then
    log "Stopped at: $failed_branch"
    if [[ -n "$in_progress" ]]; then
      log "A rebase may still be in progress on '$in_progress'."
    fi
  else
    log "All branches processed."
  fi

  printf '\n'
  log "Manual push commands (NOT executed):"
  for b in "${rebased[@]}"; do
    printf '  git push --force-with-lease origin %s\n' "$b"
  done
}

main "$@"
