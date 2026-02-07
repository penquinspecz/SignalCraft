# Contributing: Roadmap Discipline

This project treats `docs/ROADMAP.md` as an engineering contract, not a status wish-list.

## Rules

1. Every PR includes a roadmap epilogue section in the PR description.
2. A roadmap box flips only when there is deterministic evidence:
   - committed receipt paths (for receipt-gated items), and/or
   - deterministic tests for behavior claims.
3. When a box flips, include exact evidence paths in the roadmap text.
4. `Last verified: <UTC> @ <sha>` is updated only after gates are green.
5. If PR changes `ops/proof/bundles/`, PR must also update `docs/ROADMAP.md`.

## CI guard

Use `scripts/check_roadmap_discipline.py`:

- Default mode: warn-only (non-blocking).
- Strict mode: `--strict` (fails on findings).

Example:

```bash
python scripts/check_roadmap_discipline.py
python scripts/check_roadmap_discipline.py --strict
```

## PR epilogue template

Copy/paste this block into your PR description:

```md
### Roadmap Epilogue

- Boxes changed:
  - [ ] `Milestone X -> <box text>` -> changed to `[x]` because `<reason>`.
  - [ ] `Milestone Y -> <box text>` -> unchanged (receipt/test missing).
- Evidence paths:
  - `ops/proof/bundles/...`
  - `tests/...`
  - `scripts/...`
  - `docs/...`
- Last verified stamp:
  - Updated to `<UTC timestamp> @ <git sha>` only after `make lint`, `make format-check`, and `pytest -q` were green.
```
