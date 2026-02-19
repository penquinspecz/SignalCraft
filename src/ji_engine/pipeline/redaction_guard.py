from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from ji_engine.utils.redaction import scan_json_for_secrets, scan_text_for_secrets

logger = logging.getLogger(__name__)


def redaction_enforce_enabled() -> bool:
    return os.environ.get("REDACTION_ENFORCE", "").strip() == "1"


def redaction_guard_text(path: Path, text: str) -> None:
    findings = scan_text_for_secrets(text)
    if not findings:
        return
    summary = ", ".join(sorted({f"{item.pattern}@{item.location}" for item in findings}))
    msg = f"Potential secret-like content detected for {path}: {summary}"
    if redaction_enforce_enabled():
        raise RuntimeError(msg)
    logger.warning("%s (set REDACTION_ENFORCE=1 to fail closed)", msg)


def redaction_guard_json(path: Path, payload: Any) -> None:
    findings = scan_json_for_secrets(payload)
    if not findings:
        return
    summary = ", ".join(sorted({f"{item.pattern}@{item.location}" for item in findings}))
    msg = f"Potential secret-like JSON content detected for {path}: {summary}"
    if redaction_enforce_enabled():
        raise RuntimeError(msg)
    logger.warning("%s (set REDACTION_ENFORCE=1 to fail closed)", msg)
