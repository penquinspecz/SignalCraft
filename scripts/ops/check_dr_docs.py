#!/usr/bin/env python3
"""Lightweight DR docs coherence lint."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    doc: str
    needle: str


ROOT = Path(__file__).resolve().parents[2]

CHECKS: list[Check] = [
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "Canonical Entry Point"),
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "enable_triggers"),
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "control-plane/current.json"),
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "scripts/ops/dr_drill.sh"),
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "scripts/ops/dr_failback.sh"),
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "scripts/ops/dr_status.sh"),
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "scripts/ops/dr_approve.sh"),
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "TF_BACKEND_BUCKET"),
    Check("ops/dr/RUNBOOK_DISASTER_RECOVERY.md", "IMAGE_REF=<account>.dkr.ecr.us-east-1.amazonaws.com/jobintel@sha256:<digest>"),
    Check("docs/dr_promote_failback.md", "scripts/ops/dr_drill.sh"),
    Check("docs/dr_promote_failback.md", "scripts/ops/dr_failback.sh"),
    Check("docs/dr_promote_failback.md", "control-plane"),
    Check("docs/dr_orchestrator.md", "enable_triggers"),
    Check("docs/dr_orchestrator.md", "scripts/ops/dr_status.sh"),
    Check("docs/dr_orchestrator.md", "scripts/ops/dr_approve.sh"),
    Check("ops/dr/README.md", "RUNBOOK_DISASTER_RECOVERY.md"),
    Check("ops/dr/orchestrator/README.md", "enable_triggers=false"),
    Check("docs/ROADMAP.md", "DR Docs Coherence Gate: PASS"),
]

DIGEST_RE = re.compile(r"IMAGE_REF=.*@sha256:<digest>")


def main() -> int:
    failures: list[str] = []

    contents: dict[str, str] = {}
    for check in CHECKS:
        path = ROOT / check.doc
        if path.as_posix() not in contents:
            if not path.exists():
                failures.append(f"missing_doc:{check.doc}")
                continue
            contents[path.as_posix()] = path.read_text(encoding="utf-8")

        text = contents.get(path.as_posix(), "")
        if check.needle not in text:
            failures.append(f"missing_needle:{check.doc}:{check.needle}")

    runbook = contents.get((ROOT / "ops/dr/RUNBOOK_DISASTER_RECOVERY.md").as_posix(), "")
    if runbook and not DIGEST_RE.search(runbook):
        failures.append("missing_digest_ref_pattern:ops/dr/RUNBOOK_DISASTER_RECOVERY.md")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1

    print("PASS: dr_docs_coherence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
