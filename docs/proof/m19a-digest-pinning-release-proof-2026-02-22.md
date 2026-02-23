# Milestone 19A Proof - Digest Pinning Default + Release Proof Bundle (2026-02-22)

## Scope

M19A remaining DoD:
1. Non-dev deployment paths default to digest pinning (tag opt-in for development only)
2. Release proof bundle always includes metadata artifact + CI gate evidence

## 1) Digest Pinning Default

### Behavior

- **Default:** DR/operator paths require `IMAGE_REF` in digest form (`repo@sha256:<digest>`)
- **Tag (e.g. `repo:latest`):** Rejected unless `--allow-tag` or `DEV_MODE=1` / `ALLOW_TAG=1`
- **Control-plane pointer:** When IMAGE_REF comes from `control-plane/current.json`, it is already digest-pinned; no check needed

### Entrypoints Updated

| Script | Check | Override |
|--------|-------|----------|
| `dr_validate.sh` | When `image_ref_source=explicit` | `ALLOW_TAG=1` or `DEV_MODE=1` |
| `dr_drill.sh` | When `IMAGE_REF` provided | `--allow-tag` |
| `dr_restore.sh` | When `IMAGE_REF` provided | `--allow-tag` |
| `dr_failback.sh` | When `IMAGE_REF` provided | `--allow-tag` |

### Helper

`scripts/ops/assert_image_ref_digest.py` — shared assertion; exits 1 if tag and no override.

### Safe Escape Hatch

- `--allow-tag` (scripts) or `ALLOW_TAG=1` / `DEV_MODE=1` (env) for local/dev iteration
- Docs updated: `ops/dr/README.md`, `dr_drill.sh` usage

## 2) Release Proof Bundle

### Metadata Artifact

- Path: `ops/proof/releases/release-<tag>.json` (or `release-<sha>.json`)
- Written by: `scripts/release/build_and_push_ecr.sh` → `write_release_metadata.py`
- Required keys: `git_sha`, `image_repo`, `image_tag`, `image_digest`, `image_ref_digest`, `supported_architectures`, `build_timestamp`

### CI Evidence (M19A)

When built in CI (`.github/workflows/release-ecr.yml`):

- Injected into metadata: `ci_run_url`, `ci_run_id`, `ci_workflow`
- CI run URL: `$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID`
- Validated by: `scripts/release/check_release_proof_bundle.py --require-ci-evidence`

### Artifact Upload

- Name: `release-metadata-<tag>`
- Retention: 14 days
- Use: Download when creating milestone release; reference in release body

### Guardrail

`scripts/release/check_release_proof_bundle.py <path> [--require-ci-evidence]` — validates completeness.

## Gates

- `./scripts/audit_determinism.sh` — PASS
- `python3 scripts/ops/check_dr_docs.py` — PASS
- `python3 scripts/ops/check_dr_guardrails.py` — PASS

## Evidence

- `scripts/ops/assert_image_ref_digest.py`
- `scripts/ops/dr_validate.sh`, `dr_drill.sh`, `dr_restore.sh`, `dr_failback.sh` (digest check + --allow-tag)
- `.github/workflows/release-ecr.yml` (CI evidence injection)
- `scripts/release/check_release_proof_bundle.py`
- `docs/RELEASE_PROCESS.md`, `docs/VERSIONING.md` (release proof bundle)
- `ops/dr/README.md` (ALLOW_TAG for tag-based dev)
