#!/usr/bin/env python3
"""
Thin script entrypoint for the daily pipeline runner.

Behavioral implementation lives in `ji_engine.pipeline.runner`.
"""

from __future__ import annotations

import sys

try:
    import _bootstrap  # type: ignore
except ModuleNotFoundError:
    from scripts import _bootstrap  # noqa: F401

from ji_engine.pipeline import runner as _runner

main = _runner.main

if __name__ == "__main__":
    raise SystemExit(main())

# Backwards compatibility for import-time monkeypatching: expose the runner
# module directly under this module path.
sys.modules[__name__] = _runner
