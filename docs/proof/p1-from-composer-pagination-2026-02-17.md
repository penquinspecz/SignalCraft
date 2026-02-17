# P1 Fix Proof: from-composer Queue Pagination + Completeness (2026-02-17)

## Objective

Prevent silent truncation in from-composer PR collection for:
- `scripts/dev/list_from_composer_prs.sh`
- `scripts/dev/generate_codex_review_queue.sh`

## Deterministic Collection Contract

Both scripts now:
- paginate via `gh api graphql` against merged PRs labeled `from-composer`
- collect pages deterministically (GraphQL `orderBy: CREATED_AT DESC`), then emit final output sorted by `mergedAt` ascending (`mergedAt`, `number`)
- enforce explicit metadata:
  - `total_discovered`
  - `total_in_range`
  - `total_included`
  - `truncated`

## Completeness Assertion

- Default mode (no `--limit`): if the internal fetch cap is reached while more pages exist, scripts exit non-zero with a clear message.
- Intentional bounded mode (`--limit N`): scripts allow truncation and set `truncated: true` when applicable.

Internal cap control:
- `FROM_COMPOSER_INTERNAL_CAP` (default: `5000`)

Output file override for queue generation:
- `FROM_COMPOSER_OUTPUT_FILE` (useful for deterministic tests/dry-runs)

## Endpoints/Outputs Affected

- CLI output of `scripts/dev/list_from_composer_prs.sh`
- Markdown queue output of `scripts/dev/generate_codex_review_queue.sh`

## Test Evidence

Added tests in `tests/test_shell_scripts.py`:
- paginated list output includes metadata + stable ordering
- completeness assertion fails when internal cap is reached without `--limit`
- queue generation emits metadata and reports `truncated: true` when `--limit` applies

## Deterministic Dry-Run Example

```bash
FROM_COMPOSER_OUTPUT_FILE=/tmp/from-composer-queue.md \
./scripts/dev/generate_codex_review_queue.sh --since-date 2026-02-15 --limit 25
```

Expected metadata section in output includes explicit totals and truncation state.
