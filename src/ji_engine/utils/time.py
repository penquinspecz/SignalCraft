"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """
    Return a UTC datetime without tzinfo.

    This preserves legacy naive timestamp serialization while sourcing time
    from timezone-aware UTC.
    """
    return utc_now().replace(tzinfo=None)


def utc_now_iso(*, seconds_precision: bool = True) -> str:
    """Return UTC as ISO-8601 with trailing Z and deterministic precision."""
    current = utc_now()
    if seconds_precision:
        current = current.replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z")


def utc_now_z(*, seconds_precision: bool = True) -> str:
    """Backward-compatible alias for utc_now_iso."""
    return utc_now_iso(seconds_precision=seconds_precision)
