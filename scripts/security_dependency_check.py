#!/usr/bin/env python3
"""Dependency vulnerability check wrapper with retry-aware exit codes.

Exit code policy:
- Exit 0: clean scan completed with no vulnerabilities.
- Exit 1: vulnerabilities found (or non-transient audit failure).
- Exit 2: advisory infrastructure unavailable after transient retries.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from typing import Sequence

EXIT_CLEAN = 0
EXIT_VULNERABILITIES = 1
EXIT_INFRA_UNAVAILABLE = 2

_TRANSIENT_PATTERNS = (
    re.compile(r"timed out", re.IGNORECASE),
    re.compile(r"temporary failure", re.IGNORECASE),
    re.compile(r"name or service not known", re.IGNORECASE),
    re.compile(r"connection reset", re.IGNORECASE),
    re.compile(r"connection aborted", re.IGNORECASE),
    re.compile(r"connection refused", re.IGNORECASE),
    re.compile(r"tlsv1 alert", re.IGNORECASE),
    re.compile(r"max retries exceeded", re.IGNORECASE),
    re.compile(r"httpsconnectionpool", re.IGNORECASE),
    re.compile(r"read timeout", re.IGNORECASE),
    re.compile(r"service unavailable", re.IGNORECASE),
    re.compile(r"bad gateway", re.IGNORECASE),
)


def _is_transient(text: str) -> bool:
    return any(pattern.search(text) for pattern in _TRANSIENT_PATTERNS)


def _run_pip_audit(requirement_files: Sequence[str]) -> tuple[int, str]:
    os.makedirs(".cache/pip-audit", exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "--cache-dir",
        ".cache/pip-audit",
        "--progress-spinner",
        "off",
        "--no-deps",
        "--disable-pip",
    ]
    for req in requirement_files:
        cmd.extend(["-r", req])
    cp = subprocess.run(cmd, text=True, capture_output=True)
    combined = "\n".join(part for part in (cp.stdout, cp.stderr) if part).strip()
    if combined:
        print(combined)
    return cp.returncode, combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Non-flaky dependency vulnerability check wrapper for CI.")
    parser.add_argument(
        "--requirements",
        nargs="+",
        default=["requirements.txt"],
        help="Requirement files passed to pip-audit.",
    )
    parser.add_argument("--attempts", type=int, default=3, help="Max attempts for transient network failures.")
    parser.add_argument("--sleep-seconds", type=float, default=5.0, help="Delay between transient retries.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    attempts = max(1, args.attempts)
    for attempt in range(1, attempts + 1):
        print(f"dependency audit attempt {attempt}/{attempts}")
        rc, output = _run_pip_audit(args.requirements)
        if rc == EXIT_CLEAN:
            print("dependency audit passed")
            return EXIT_CLEAN
        if _is_transient(output):
            if attempt < attempts:
                print("transient dependency-audit failure detected; retrying")
                time.sleep(max(0.0, args.sleep_seconds))
                continue
            print("WARNING: dependency audit unavailable after retries (transient network/service failure); exiting 2")
            return EXIT_INFRA_UNAVAILABLE
        print(f"dependency audit found vulnerabilities (exit={rc})")
        return EXIT_VULNERABILITIES
    return EXIT_INFRA_UNAVAILABLE


if __name__ == "__main__":
    raise SystemExit(main())
