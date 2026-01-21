from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import requests

DEFAULT_MIN_BYTES = 50_000
BLOCKED_MARKERS = (
    "captcha",
    "access denied",
    "cloudflare",
    "forbidden",
    "verify you are human",
    "temporarily blocked",
    "request blocked",
    "attention required",
)


def fetch_html(url: str, headers: dict[str, str], timeout: float) -> Tuple[str, int, Optional[str]]:
    resp = requests.get(url, headers=headers, timeout=timeout)
    content_type = resp.headers.get("Content-Type")
    return resp.text, resp.status_code, content_type


def is_valid_snapshot(html: str, min_bytes: int = DEFAULT_MIN_BYTES) -> Tuple[bool, str]:
    if not html:
        return False, "empty response"

    lower = html.lower()
    if "<!doctype html" not in lower and "<html" not in lower and "</html" not in lower:
        return False, "missing html tags"

    for marker in BLOCKED_MARKERS:
        if marker in lower:
            return False, f"blocked marker: {marker}"

    byte_len = len(html.encode("utf-8"))
    if byte_len < min_bytes:
        return False, f"content too small ({byte_len} bytes)"

    return True, "ok"


def write_snapshot(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(html)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def maybe_write_snapshot(
    path: Path,
    html: str,
    *,
    force: bool,
    min_bytes: int = DEFAULT_MIN_BYTES,
) -> Tuple[bool, str]:
    valid, reason = is_valid_snapshot(html, min_bytes=min_bytes)
    if not valid and not force:
        return False, reason
    write_snapshot(path, html)
    if valid:
        return True, reason
    return True, f"forced write (invalid snapshot: {reason})"


def refresh_snapshot(
    provider_id: str,
    url: str,
    out_path: Path,
    *,
    force: bool = False,
    timeout: float = 20.0,
    min_bytes: int = DEFAULT_MIN_BYTES,
    headers: Optional[dict[str, str]] = None,
    logger: Optional[logging.Logger] = None,
) -> int:
    if logger is None:
        logger = logging.getLogger(__name__)

    req_headers = dict(headers or {})
    req_headers.setdefault("User-Agent", "job-intelligence-engine/0.1 (+snapshot-refresh)")
    req_headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

    logger.info("Refreshing snapshot for %s from %s", provider_id, url)

    try:
        html, status_code, content_type = fetch_html(url, req_headers, timeout)
    except requests.RequestException as exc:
        logger.error("Fetch failed for %s: %s", provider_id, exc)
        return 1

    if status_code != 200:
        reason = f"http status {status_code}"
        if not force:
            logger.error("Snapshot fetch failed for %s: %s", provider_id, reason)
            return 1
        logger.warning("Forcing snapshot write despite %s", reason)

    if content_type and "html" not in content_type.lower():
        reason = f"content-type {content_type}"
        if not force:
            logger.error("Invalid snapshot for %s: %s", provider_id, reason)
            return 1
        logger.warning("Forcing snapshot write despite %s", reason)

    valid, reason = is_valid_snapshot(html, min_bytes=min_bytes)
    if not valid and not force:
        logger.error("Invalid snapshot for %s: %s", provider_id, reason)
        return 1
    if not valid and force:
        logger.warning("Forcing snapshot write despite invalid content: %s", reason)

    write_snapshot(out_path, html)
    size_bytes = len(html.encode("utf-8"))
    logger.info("Wrote snapshot for %s to %s (%d bytes)", provider_id, out_path, size_bytes)
    return 0

