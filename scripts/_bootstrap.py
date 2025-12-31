# scripts/_bootstrap.py
from __future__ import annotations

import sys
from pathlib import Path

def ensure_src_on_path() -> None:
    """
    Ensures <repo>/src is on sys.path so `import ji_engine` works
    even when the project is not installed as a package.

    Safe to call multiple times.
    """
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))