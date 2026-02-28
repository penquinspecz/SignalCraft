#!/usr/bin/env python3
"""Redact CloudWatch pagination token values in exported JSON artifacts.

This keeps proof JSON shape stable while removing token material that can trip
secret scanners when committed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REDACTED = "<REDACTED>"
TOKEN_KEY_RE = re.compile(r"^next.*token$", re.IGNORECASE)


def _redact(node: Any) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if TOKEN_KEY_RE.match(key):
                out[key] = REDACTED
            else:
                out[key] = _redact(value)
        return out
    if isinstance(node, list):
        return [_redact(item) for item in node]
    return node


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input JSON file")
    parser.add_argument("--output", required=True, help="Output JSON file")
    args = parser.parse_args()

    src = Path(args.input)
    dst = Path(args.output)

    payload = json.loads(src.read_text(encoding="utf-8"))
    redacted = _redact(payload)
    dst.write_text(json.dumps(redacted, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
