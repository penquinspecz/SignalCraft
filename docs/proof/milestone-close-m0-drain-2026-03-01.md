# Milestone Close + M0 Drain Proof (2026-03-01)

## Scope
- Merge remaining open PRs with checks-green + pr-governance gates.
- Close completed milestones (no open items).
- Close empty placeholder milestones by default.
- Keep only explicitly active/parked empty roadmap milestones open.
- Drain `M0 - Triage` open issues and enforce triage-bucket policy text.

## PR Merge Results
- Merge train executed in safe order:
  - `#274` -> merged
  - `#275` -> merged
  - `#276` -> conflict, rebased, merged
  - `#277` -> conflict, rebased, merged
- Final open PR count: `0`

## Milestone Policy Applied
Tool: `scripts/dev/cleanup_milestones.py`

Policy:
- `open_count > 0` => keep/open
- `open_count == 0 && closed_count > 0` => close
- `open_count == 0 && closed_count == 0` => close unless roadmap section marks milestone as ACTIVE/PARKED
- `M0 - Triage` kept open as triage bucket

## Before/After Snapshot
- before: `open=22`, `closed=15`
- after: `open=7`, `closed=30`

Open milestones after apply:
- `M27` (active placeholder)
- `M31` (active placeholder)
- `M32` (active placeholder)
- `M33` (active placeholder)
- `M40` (parked placeholder)
- `M41` (parked placeholder)
- `M0 - Triage` (triage bucket; open items now `0`)

## M0 Drain Decision
Tool: `scripts/dev/rehoming_milestones.py --drain-m0-open`

- Open issues in `M0 - Triage` at execution time: `0`
- Rehomed from M0: `0`
- Ambiguous left in M0: `0`
- `M0 - Triage` description updated to:
  - "Only ambiguous items allowed. Add explicit `Milestone <N>` or `M<N>` context in issue body for deterministic rehome."

This leaves M0 drained to zero open issues while preserving an explicit policy for future ambiguous intake.

## Commands Executed
- `python3 scripts/dev/cleanup_milestones.py --report docs/proof/milestones-close-policy-dry-2026-03-01.md`
- `python3 scripts/dev/cleanup_milestones.py --apply --report docs/proof/milestones-close-policy-apply-2026-03-01.md`
- `python3 scripts/dev/rehoming_milestones.py --drain-m0-open --dry-run`
- `python3 scripts/dev/rehoming_milestones.py --drain-m0-open --apply`
- `python3 scripts/dev/rehoming_milestones.py --drain-m0-open --verify`
- `gh pr list --state open --json number,title`
- `gh issue list --state open --milestone "M0 - Triage" --json number,title,url`

## Validation
- `make format`
- `make lint`
- `make ci-fast`
- `make gate`
