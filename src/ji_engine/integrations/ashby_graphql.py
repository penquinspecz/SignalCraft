from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

# Import the existing implementation for now (temporary bridge)
# We'll delete the scripts/* version later once everything points here.
from scripts.ashby_graphql import fetch_job_posting  # type: ignore[F401]


__all__ = ["fetch_job_posting"]