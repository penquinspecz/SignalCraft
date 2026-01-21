from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from .refresh import BLOCKED_MARKERS, DEFAULT_MIN_BYTES


@dataclass(frozen=True)
class ValidationResult:
    provider: str
    path: Path
    ok: bool
    reason: str


def _default_data_dir() -> Path:
    return Path(os.environ.get("JOBINTEL_DATA_DIR") or "data")


def _snapshot_path_for(provider: str, data_dir: Path) -> Path:
    if provider == "openai":
        return data_dir / "openai_snapshots" / "index.html"
    if provider == "anthropic":
        return data_dir / "anthropic_snapshots" / "index.html"
    raise ValueError(f"Unknown provider '{provider}'.")


def _looks_blocked(html: str) -> Tuple[bool, str]:
    lower = html.lower()
    for marker in BLOCKED_MARKERS:
        if marker in lower:
            return True, f"blocked marker: {marker}"
    return False, "ok"


def validate_snapshot_file(path: Path, *, min_bytes: int = DEFAULT_MIN_BYTES) -> Tuple[bool, str]:
    if not path.exists():
        return False, "missing file"

    try:
        data = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return False, f"read failed: {exc}"

    if not data.strip():
        return False, "empty file"

    byte_len = len(data.encode("utf-8"))
    if byte_len < min_bytes:
        return False, f"file too small ({byte_len} bytes)"

    blocked, reason = _looks_blocked(data)
    if blocked:
        return False, reason

    if "<html" not in data.lower() and "<!doctype html" not in data.lower():
        return False, "missing html tags"

    return True, "ok"


def validate_snapshots(
    providers: Iterable[str],
    *,
    data_dir: Path | None = None,
    min_bytes: int = DEFAULT_MIN_BYTES,
) -> List[ValidationResult]:
    base_dir = data_dir or _default_data_dir()
    results: List[ValidationResult] = []
    for provider in providers:
        snapshot_path = _snapshot_path_for(provider, base_dir)
        ok, reason = validate_snapshot_file(snapshot_path, min_bytes=min_bytes)
        results.append(ValidationResult(provider=provider, path=snapshot_path, ok=ok, reason=reason))
    return results
