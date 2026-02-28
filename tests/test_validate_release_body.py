from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "release" / "validate_release_body.py"


def _run_validator(tmp_path: Path, body: str, *args: str) -> subprocess.CompletedProcess[str]:
    body_path = tmp_path / "release.md"
    body_path.write_text(body, encoding="utf-8")
    cmd = [sys.executable, str(VALIDATOR), "--body-file", str(body_path), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_product_minor_passes(tmp_path: Path) -> None:
    body = """
# SignalCraft Product Release v0.2.1

## Highlights
- Added deterministic release notes validator.

## What's Proven (Operator Reality Check)
- Release body validation blocks malformed release notes.

## Images (Digest-pinned)
- IMAGE_REF: `123456789012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
- Digest: `sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`

## Upgrade / Operational Notes
- None

## Changes (categorized)
- Added:
  - Release body validator.
- Changed:
  - None
- Fixed:
  - None

## Breaking Changes
- None

## Known Issues
- None

## Proof References
- docs/proof/example.md

## Integrity
- Main commit SHA: `1111111111111111111111111111111111111111`
- IMAGE_REF digest: `sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
- CI workflow URL: `https://github.com/penquinspecz/SignalCraft/actions/runs/123`
- CI run ID: `123`
- CI workflow: `release-ecr`
""".strip()
    proc = _run_validator(
        tmp_path,
        body,
        "--release-kind",
        "product",
        "--semver-level",
        "minor",
        "--tag",
        "v0.2.1",
        "--require-ci-evidence",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_product_fails_without_digest_pinned_image_ref(tmp_path: Path) -> None:
    body = """
# SignalCraft Product Release v0.2.1

## Highlights
- None
## What's Proven (Operator Reality Check)
- None
## Images (Digest-pinned)
- IMAGE_REF: `123456789012.dkr.ecr.us-east-1.amazonaws.com/jobintel:latest`
- Digest: `Not recorded at tag time`
## Upgrade / Operational Notes
- None
## Changes (categorized)
- Added:
  - None
- Changed:
  - None
- Fixed:
  - None
## Breaking Changes
- None
## Known Issues
- None
## Proof References
- docs/proof/example.md
## Integrity
- Main commit SHA: `1111111111111111111111111111111111111111`
- IMAGE_REF digest: `Not recorded at tag time`
- CI workflow URL: `https://github.com/penquinspecz/SignalCraft/actions/runs/123`
- CI run ID: `123`
- CI workflow: `release-ecr`
""".strip()
    proc = _run_validator(tmp_path, body, "--release-kind", "product", "--tag", "v0.2.1")
    assert proc.returncode != 0
    assert "digest-pinned IMAGE_REF is required" in proc.stdout


def test_milestone_passes(tmp_path: Path) -> None:
    body = """
# SignalCraft Milestone Release m19-20260222T201429Z

## Milestone Context
- milestone_tag: `m19-20260222T201429Z`
- Main commit SHA: `2222222222222222222222222222222222222222`
- intent: prove success-path to manual gate

## What was exercised
- success path through request_manual_approval

## Execution Evidence
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19`
- terminal_state: `RequestManualApproval`
- terminal_status: `ABORTED`
- receipts_root: `docs/proof/receipts-m19/`

## Images (Digest-pinned)
- IMAGE_REF: `123456789012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb`
- Digest: `sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb`

## Guardrails/Determinism checks
- ./scripts/audit_determinism.sh: PASS

## Outcome + Next steps
- outcome: success path proven to manual gate
- next_step: none

## Proof References
- docs/proof/m19.md
""".strip()
    proc = _run_validator(tmp_path, body, "--release-kind", "milestone", "--tag", "m19-20260222T201429Z")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_major_fails_without_migration_guide(tmp_path: Path) -> None:
    body = """
# SignalCraft Product Release v1.0.0

## Highlights
- Major release.
## What's Proven (Operator Reality Check)
- None
## Images (Digest-pinned)
- IMAGE_REF: `123456789012.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc`
- Digest: `sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc`
## Upgrade / Operational Notes
- None
## Changes (categorized)
- Added:
  - None
- Changed:
  - None
- Fixed:
  - None
## Breaking Changes
- None
## Known Issues
- None
## Proof References
- docs/proof/v1.md
## Why this release exists
- New major contract.
## Compatibility Matrix
- None
## Deprecations Timeline
- None
## Integrity
- Main commit SHA: `3333333333333333333333333333333333333333`
- IMAGE_REF digest: `sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc`
- CI workflow URL: `https://github.com/penquinspecz/SignalCraft/actions/runs/999`
- CI run ID: `999`
- CI workflow: `release-ecr`
""".strip()
    proc = _run_validator(
        tmp_path,
        body,
        "--release-kind",
        "product",
        "--semver-level",
        "major",
        "--tag",
        "v1.0.0",
    )
    assert proc.returncode != 0
    assert "missing required heading: 'Migration / Upgrade Guide'" in proc.stdout
