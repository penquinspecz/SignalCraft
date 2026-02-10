# Proof Storage Contract

This document defines the storage contract for proof bundles under `ops/proof/bundles/`.

## Naming convention

- Bundle root: `ops/proof/bundles/m<milestone>-<run_id>/`
- Component subdir: `<bundle_root>/<component>/`
- Required metadata files per component:
  - `receipt.json`
  - `manifest.json`

Examples:

- `ops/proof/bundles/m3-2026-02-07T03:27:56Z/infra/`
- `ops/proof/bundles/m4-local/eks_infra/`

## `receipt.json` required keys

`receipt.json` must be a JSON object and include at least:

- `schema_version` (integer)
- `run_id` (string)
- `mode` (string, e.g. `plan`, `execute`)
- `captured_at` (UTC timestamp string)

Component-specific keys may be added, but core keys above are mandatory.

## `manifest.json` rules

`manifest.json` must be a JSON object with:

- `schema_version` (integer)
- `run_id` (string)
- `files` (array)

Each file entry must include:

- `path` (relative file path string)
- `sha256` (hex digest string)
- `size_bytes` (integer)

Determinism rules:

- `files` must use stable ordering (`path` ascending).
- Hashes and sizes must reflect on-disk content exactly.
- Manifest serialization must be stable (`sort_keys=true` style output).

## Storage targets

Allowed targets:

- Local filesystem (default): `ops/proof/bundles/`
- S3 object storage (optional mirror/archive target)

When storing in S3, preserve relative path layout exactly.

## Secret handling

Do not store secrets in proof bundles.

- Redact secret-like values before writing logs/artifacts.
- Never include API keys, webhook tokens, AWS secret keys, or bearer tokens.
- If a capture source may contain credentials, write a redacted version only.
