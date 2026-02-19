from __future__ import annotations

from pathlib import Path


def sanitize_run_id(run_id: str) -> str:
    """Normalize run IDs into filesystem-safe directory names."""
    return run_id.replace(":", "").replace("-", "").replace(".", "")


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
