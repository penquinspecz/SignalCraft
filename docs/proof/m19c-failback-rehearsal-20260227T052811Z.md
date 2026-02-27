# M19C Deterministic Failback Rehearsal (2026-02-27T05:28:11Z)

- Main SHA: `0f08a365e324500cb6eae744bbe13e5fef0200f8`
- Branch: `chore/m19c-failback-rehearsal-20260227T052317Z`
- Bucket/Prefix under test: `jobintel-prod1` / `jobintel`
- Provider/Profile: `openai` / `cs`
- Run IDs used:
  - `dr-run-id`: `2026-02-27T00:22:29.934039+00:00`
  - `primary-run-id`: `2026-02-27T00:22:29.934039+00:00`

## Commands Executed

```bash
AWS_PROFILE=signalcraft-ops ./scripts/ops/dr_failback_pointers.sh \
  --bucket jobintel-prod1 \
  --prefix jobintel \
  --primary-run-id 2026-02-27T00:22:29.934039+00:00 \
  --dr-run-id 2026-02-27T00:22:29.934039+00:00 \
  --receipt-dir docs/proof/receipts-m19c-dryrun-20260227T052745Z \
  --dry-run

AWS_PROFILE=signalcraft-ops ./scripts/ops/dr_failback_pointers.sh \
  --bucket jobintel-prod1 \
  --prefix jobintel \
  --primary-run-id 2026-02-27T00:22:29.934039+00:00 \
  --dr-run-id 2026-02-27T00:22:29.934039+00:00 \
  --receipt-dir docs/proof/receipts-m19c-apply-20260227T052811Z \
  --apply
```

## Required Receipts

Dry-run receipt dir: `docs/proof/receipts-m19c-dryrun-20260227T052745Z/`
- `drill.failback.inputs.json`
- `drill.failback.verify_before.json`
- `drill.failback.plan.json`
- `drill.failback.phase_timestamps.json`

Apply receipt dir: `docs/proof/receipts-m19c-apply-20260227T052811Z/`
- `drill.failback.apply.json`
- `drill.failback.verify_after.json`
- `drill.failback.verify_before.json`
- `drill.failback.plan.json`
- `drill.failback.phase_timestamps.json`

## Plan/Apply Validation

- Plan keys limited to expected pointer keys:
  - `jobintel/state/last_success.json`
  - `jobintel/state/openai/cs/last_success.json`
- Plan from/to run IDs are identical (no unintended switch):
  - `from_run_id == to_run_id == 2026-02-27T00:22:29.934039+00:00`
- Receipt bucket/prefix values match expected stable state (`jobintel-prod1` / `jobintel`).

## Drift and Artifact Checks

Additional before/after snapshots captured around apply:
- `docs/proof/m19c-pointers-preapply-20260227T052811Z.json`
- `docs/proof/m19c-pointers-postapply-20260227T052811Z.json`
- `docs/proof/m19c-run-objects-preapply-20260227T052811Z.json`
- `docs/proof/m19c-run-objects-postapply-20260227T052811Z.json`
- `docs/proof/m19c-apply-diff-summary-20260227T052811Z.json`

Diff summary result:
- `pointer_changed=false`
- `objects_changed=false`

No pointer drift observed.

No artifact loss observed.
