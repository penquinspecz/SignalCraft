from __future__ import annotations

import re
from pathlib import Path

_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9T_Z]+$")


def sanitize_run_id(run_id: str) -> str:
    """Normalize run IDs into filesystem-safe directory names.

    Strips timestamp separators (`:`, `-`, `.`) then validates that the result
    contains only safe characters. Rejects any run_id that would contain path
    separators, traversal sequences, or other unsafe characters.

    Raises ValueError if the sanitized run_id contains unsafe characters.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError(f"Invalid run_id: {run_id!r}")

    raw = run_id.strip()
    # Backward compatibility: normalize UTC offset form into canonical Z suffix.
    if raw.endswith("+00:00"):
        raw = f"{raw[:-6]}Z"

    sanitized = raw.replace(":", "").replace("-", "").replace(".", "")

    if not _RUN_ID_PATTERN.fullmatch(sanitized):
        raise ValueError(
            f"Unsafe run_id after sanitization: {sanitized!r} "
            f"(original: {run_id!r}). "
            f"Run IDs must match {_RUN_ID_PATTERN.pattern}"
        )

    return sanitized


def resolve_run_path(base_dir, run_id: str) -> Path:
    """Resolve a run directory path with boundary enforcement.

    Returns the resolved path and verifies it is within base_dir.
    Raises ValueError if the resolved path escapes the base directory.
    """
    base = Path(base_dir).resolve()
    sanitized = sanitize_run_id(run_id)
    run_path = (base / sanitized).resolve()

    try:
        run_path.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Run path {run_path} escapes base directory {base}") from exc

    return run_path


def summary_path_text(path: Path, *, repo_root: Path) -> str:
    """Return a stable display path relative to repo root when possible."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_summary_path(path_value: str, *, repo_root: Path) -> Path:
    """Resolve persisted summary path pointers from absolute or repo-relative values."""
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()
