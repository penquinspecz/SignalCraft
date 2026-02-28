# PR Area Label Retrofix (20260228T045022Z)

## Scope
- Reviewed the last 50 closed PRs via `gh pr list --state closed --limit 50`.
- Applied deterministic label cleanup rules for `area:docs`, `area:dr`, `area:infra`, and `area:release`.
- Preserved non-area labels (`type:*`, `from-*`, milestone labels).

## Inputs
- Snapshot JSON: `docs/proof/pr-area-label-retrofix-snapshot-20260228T045022Z.json`

## Rules Used
- Keep `area:docs` only when PR is docs-dominant (>=70% `docs/**`) and has no DR/infra/release signals.
- Add `area:dr` for `ops/dr/**` or DR/orchestrator-related scripts/signals.
- Add `area:infra` for Terraform/IAM/infra wiring signals (`.tf`, terraform paths, IAM-related paths).
- Add `area:release` for `scripts/release/**` or release workflows.
- Remove `area:docs` when above docs-only condition is not met.

## Result
- PRs relabeled: **27**

| PR | Before | After | Added | Removed | Reason |
|---:|---|---|---|---|---|
| [#196](https://github.com/penquinspecz/SignalCraft/pull/196) | (none) | area:docs | area:docs | (none) | docs-dominant and no infra/dr/release signals |
| [#198](https://github.com/penquinspecz/SignalCraft/pull/198) | (none) | area:docs | area:docs | (none) | docs-dominant and no infra/dr/release signals |
| [#200](https://github.com/penquinspecz/SignalCraft/pull/200) | (none) | area:docs | area:docs | (none) | docs-dominant and no infra/dr/release signals |
| [#201](https://github.com/penquinspecz/SignalCraft/pull/201) | (none) | area:docs | area:docs | (none) | docs-dominant and no infra/dr/release signals |
| [#203](https://github.com/penquinspecz/SignalCraft/pull/203) | (none) | area:docs | area:docs | (none) | docs-dominant and no infra/dr/release signals |
| [#205](https://github.com/penquinspecz/SignalCraft/pull/205) | (none) | area:docs | area:docs | (none) | docs-dominant and no infra/dr/release signals |
| [#207](https://github.com/penquinspecz/SignalCraft/pull/207) | (none) | area:docs | area:docs | (none) | docs-dominant and no infra/dr/release signals |
| [#208](https://github.com/penquinspecz/SignalCraft/pull/208) | (none) | area:docs | area:docs | (none) | docs-dominant and no infra/dr/release signals |
| [#212](https://github.com/penquinspecz/SignalCraft/pull/212) | (none) | area:dr | area:dr | (none) | DR paths/signals present |
| [#213](https://github.com/penquinspecz/SignalCraft/pull/213) | (none) | area:dr, area:infra, area:release | area:dr, area:infra, area:release | (none) | DR paths/signals present; Terraform/IAM/infra signal present; release script/workflow signal present |
| [#214](https://github.com/penquinspecz/SignalCraft/pull/214) | (none) | area:dr | area:dr | (none) | DR paths/signals present |
| [#215](https://github.com/penquinspecz/SignalCraft/pull/215) | (none) | area:dr | area:dr | (none) | DR paths/signals present |
| [#216](https://github.com/penquinspecz/SignalCraft/pull/216) | (none) | area:dr | area:dr | (none) | DR paths/signals present |
| [#217](https://github.com/penquinspecz/SignalCraft/pull/217) | area:docs, area:dr | area:dr | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#218](https://github.com/penquinspecz/SignalCraft/pull/218) | area:docs, area:dr, area:release | area:dr, area:release | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#221](https://github.com/penquinspecz/SignalCraft/pull/221) | area:docs | (none) | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#222](https://github.com/penquinspecz/SignalCraft/pull/222) | area:docs | (none) | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#228](https://github.com/penquinspecz/SignalCraft/pull/228) | area:docs, area:release | area:release | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#230](https://github.com/penquinspecz/SignalCraft/pull/230) | area:docs, area:dr, area:infra | area:dr, area:infra | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#232](https://github.com/penquinspecz/SignalCraft/pull/232) | area:docs, area:dr, area:infra | area:dr, area:infra | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#233](https://github.com/penquinspecz/SignalCraft/pull/233) | area:docs, area:dr, area:infra, area:release | area:dr, area:infra, area:release | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#235](https://github.com/penquinspecz/SignalCraft/pull/235) | area:docs, area:dr, area:infra | area:dr, area:infra | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#236](https://github.com/penquinspecz/SignalCraft/pull/236) | area:docs, area:dr, area:infra | area:dr, area:infra | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#237](https://github.com/penquinspecz/SignalCraft/pull/237) | area:docs, area:dr, area:infra | area:dr, area:infra | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#238](https://github.com/penquinspecz/SignalCraft/pull/238) | area:docs, area:dr, area:infra | area:dr, area:infra | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#239](https://github.com/penquinspecz/SignalCraft/pull/239) | area:docs, area:release | area:release | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
| [#241](https://github.com/penquinspecz/SignalCraft/pull/241) | area:docs, area:release | area:release | (none) | area:docs | docs label removed: not docs-dominant docs-only scope |
