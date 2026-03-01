"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

# src/ji_engine/providers/base.py

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ji_engine.models import RawJobPosting
from ji_engine.utils.network_shield import NetworkShieldError

logger = logging.getLogger(__name__)


class BaseJobProvider(ABC):
    """
    Base provider that handles mode selection and snapshot fallback.

    Modes:
      - SNAPSHOT: only load from local HTML/JSON
      - LIVE: try HTTP scrape, on error fall back to snapshot
    """

    def __init__(self, mode: str = "SNAPSHOT", data_dir: str = "data"):
        self.mode = mode.upper()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._fallback_triggered = False
        self._fallback_reason: str | None = None

    def fetch_jobs(self) -> List[RawJobPosting]:
        """Top-level orchestrator for fetching jobs."""
        self._fallback_triggered = False
        self._fallback_reason = None
        if self.mode == "SNAPSHOT":
            print(f"[{self.__class__.__name__}] Mode=SNAPSHOT → loading from snapshot")
            return self.load_from_snapshot()
        else:
            print(f"[{self.__class__.__name__}] Mode=LIVE → attempting live scrape")
            try:
                return self.scrape_live()
            except NetworkShieldError:
                raise
            except (ConnectionError, TimeoutError, OSError) as exc:
                logger.warning(
                    "[%s] Live scrape failed (network), falling back to snapshot: %s",
                    self.__class__.__name__,
                    exc,
                )
                self._fallback_triggered = True
                self._fallback_reason = f"{type(exc).__name__}: {exc}"
                return self.load_from_snapshot()
            except Exception as exc:
                logger.error(
                    "[%s] Live scrape failed (unexpected), falling back to snapshot: %s",
                    self.__class__.__name__,
                    exc,
                )
                self._fallback_triggered = True
                self._fallback_reason = f"{type(exc).__name__}: {exc}"
                return self.load_from_snapshot()

    @abstractmethod
    def scrape_live(self) -> List[RawJobPosting]:
        """Implement HTTP-based scraping here."""
        raise NotImplementedError

    @abstractmethod
    def load_from_snapshot(self) -> List[RawJobPosting]:
        """Implement snapshot-based parsing here."""
        raise NotImplementedError
