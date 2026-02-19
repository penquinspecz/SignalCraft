# From-Composer Audit Workflow (2026-02-15)

## Summary

Tooling to prepare a Codex-friendly audit of merged PRs labeled `from-composer`. When Codex quota returns, run these scripts to generate a review queue and programmatically trigger reviews.

This workflow is intentionally **composer-specific**. Do not reuse `from-composer` for Codex-authored or human-authored PRs.
Use provenance labels consistently:
- `from-composer`: Composer workflow/tooling output
- `from-codex`: Codex-authored/executed changes
- no provenance label required for other branch prefixes

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/dev/list_from_composer_prs.sh` | List merged from-composer PRs with metadata and files |
| `scripts/dev/generate_codex_review_queue.sh` | Generate markdown queue with paste-ready Codex review prompts |

## GitHub Action (optional)

`.github/workflows/codex-review-queue.yml` — manual `workflow_dispatch`:

1. Actions → codex-review-queue → Run workflow
2. Optionally set `since_date` (YYYY-MM-DD)
3. Artifact `codex-review-queue` contains the generated markdown

Uses default `GITHUB_TOKEN`; no extra secrets.

## Usage

```bash
# List merged from-composer PRs (default: last 7 days)
./scripts/dev/list_from_composer_prs.sh

# Since a specific date
./scripts/dev/list_from_composer_prs.sh --since-date 2026-02-15

# Since a commit (uses that commit's date)
./scripts/dev/list_from_composer_prs.sh --since-commit 5e1491a

# Limit number of PRs
./scripts/dev/list_from_composer_prs.sh --since-date 2026-02-01 --limit 10

# Generate Codex review queue (writes docs/proof/from-composer-codex-review-queue-YYYY-MM-DD.md)
./scripts/dev/generate_codex_review_queue.sh
./scripts/dev/generate_codex_review_queue.sh --since-date 2026-02-15 --limit 20
```

## Prerequisites

- `gh` CLI (authenticated)
- `jq`

## Output

### list_from_composer_prs.sh

Per-PR lines:
- PR number, title
- Merge commit SHA
- Branch name
- Merged timestamp
- URL
- Files changed (top 20)

### generate_codex_review_queue.sh

Writes `docs/proof/from-composer-codex-review-queue-YYYY-MM-DD.md` with:
- One section per PR
- PR link, merge SHA, files list
- Collapsible `<details>` block with paste-ready Codex review prompt

Review prompt focuses on:
1. Determinism
2. Security (filesystem/network, input validation)
3. Replay (artifact schemas, metadata contracts)
4. Regression (tests, gate conditions)

## Zero PRs

Both scripts handle empty ranges:
- `list_from_composer_prs.sh`: prints "No merged from-composer PRs in range" and exits 0
- `generate_codex_review_queue.sh`: writes minimal markdown with "No PRs in range"

## Determinism

- No external APIs beyond `gh` CLI
- Inputs: --since-date, --since-commit, --limit
- Output is deterministic for same inputs

## Sample queue output (top)

```markdown
# From-Composer Codex Review Queue (2026-02-15)

Generated: 2026-02-15T23:55:13Z

## Scope
Since: 2026-02-15

## PRs

### PR #154: feat(dashboard): M17 API boring pack smoke + negative coverage

- **URL:** https://github.com/penquinspecz/SignalCraft/pull/154
- **Merge SHA:** `2c0d8166c20f9475cf4999cd251032c9d37b5d40`
- **Files changed:**
  - docs/proof/m17-api-boring-pack-smoke-negative-2026-02-15.md
  - scripts/dev/curl_dashboard_proof.sh
  - scripts/dev/dashboard_contract_smoke.sh
  - tests/test_dashboard_app.py

<details>
<summary>Codex review prompt (paste-ready)</summary>
...
</details>
```
