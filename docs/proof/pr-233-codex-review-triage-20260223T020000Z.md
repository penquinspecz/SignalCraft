# PR #233 Codex Review Triage

- **PR:** 233
- **Branch:** chore/m19a-digest-pinning-release-proof-20260222
- **Initial commit SHA:** 6c15fda7f5dd47e208549e902613823aade83b7d
- **Reviewed by:** chatgpt-codex-connector
- **Triage timestamp:** 2026-02-23T02:00:00Z

## Codex Comments

### 1. P1 — Remove default array fallback in digest assertion call

**File:** `scripts/ops/dr_drill.sh` (line 233); same pattern in `dr_restore.sh`, `dr_failback.sh`

**Finding:** Using `"${allow_tag_arg[@]:-}"` injects an empty argument when `allow_tag_arg` is empty, so `assert_image_ref_digest.py` receives an extra positional and exits with `unrecognized arguments:`; valid digest refs fail when `--allow-tag` is not set.

**Decision:** [x] Applied

**Fix:** Replace `"${allow_tag_arg[@]:-}"` with `"${allow_tag_arg[@]}"` so empty array expands to zero arguments.

---

### 2. P2 — Enforce digest validation for resolved control-plane refs

**File:** `scripts/ops/dr_validate.sh` (line 133)

**Finding:** Gate only runs when `image_ref_source` is `explicit`. If IMAGE_REF is resolved from `control-plane/current.json`, no digest assertion is applied; a tag-valued `image_ref_digest` could flow through.

**Decision:** [x] Applied

**Fix:** Apply assertion to any non-empty `resolved_image_ref` (remove `image_ref_source == "explicit"` condition). Control-plane source should already be digest from publish_bundle, but defensive validation keeps digest-only as true default.

---

### 3. P3 — Require ci_workflow in proof-bundle CI evidence checks

**File:** `scripts/release/check_release_proof_bundle.py` (line 27)

**Finding:** `--require-ci-evidence` validates only `ci_run_url` and `ci_run_id`; metadata missing `ci_workflow` still passes even though workflow injects it.

**Decision:** [x] Applied

**Fix:** Add `ci_workflow` to `CI_EVIDENCE_KEYS`.

---

## Validation Commands

```bash
./scripts/audit_determinism.sh
python3 scripts/ops/check_dr_docs.py
python3 scripts/ops/check_dr_guardrails.py
make lint
make ci-fast
```

## Final Status

- **Codex fixes commit:** 012fd12
- **All gates:** PASS (audit_determinism, check_dr_docs, check_dr_guardrails, make lint)
