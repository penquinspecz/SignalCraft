from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import requests

from .validate import MIN_BYTES_DEFAULT, validate_snapshot_bytes


def fetch_html(url: str, headers: dict[str, str], timeout: float) -> Tuple[bytes, int, Optional[str]]:
    resp = requests.get(url, headers=headers, timeout=timeout)
    content_type = resp.headers.get("Content-Type")
    return resp.content, resp.status_code, content_type


def write_snapshot(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def refresh_snapshot(
    provider_id: str,
    url: str,
    out_path: Path,
    *,
    force: bool = False,
    timeout: float = 20.0,
    min_bytes: int = MIN_BYTES_DEFAULT,
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
        content, status_code, _content_type = fetch_html(url, req_headers, timeout)
    except requests.RequestException as exc:
        logger.error("Fetch failed for %s: %s", provider_id, exc)
        return 1

    if status_code != 200:
        reason = f"http status {status_code}"
        if not force:
            logger.error("Snapshot fetch failed for %s: %s", provider_id, reason)
            return 1
        logger.warning("Forcing snapshot write despite %s", reason)

    if min_bytes != MIN_BYTES_DEFAULT:
        os.environ["JOBINTEL_SNAPSHOT_MIN_BYTES"] = str(min_bytes)
    valid, reason = validate_snapshot_bytes(provider_id, content)
    if not valid and not force:
        logger.error("Invalid snapshot for %s: %s", provider_id, reason)
        return 1
    if not valid and force:
        logger.warning("Forcing snapshot write despite invalid content: %s", reason)

    write_snapshot(out_path, content)
    size_bytes = len(content)
    logger.info("Wrote snapshot for %s to %s (%d bytes)", provider_id, out_path, size_bytes)
    return 0
