"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from typing import Literal, Optional, Tuple

from ji_engine.providers.retry import evaluate_allowlist_policy
from ji_engine.utils.network_shield import NetworkShieldError, safe_get_text, validate_url_destination
from ji_engine.utils.time import utc_now_z

FetchMethod = Literal["requests", "playwright"]
_FETCH_MAX_BYTES = 2_000_000
_FETCH_MAX_REDIRECTS = 5
_META_TEXT_LIMIT = 2048
_META_ERROR_LIMIT = 512


def _utcnow_iso() -> str:
    return utc_now_z(seconds_precision=True)


def _clip(value: Optional[str], *, limit: int) -> Optional[str]:
    if value is None:
        return None
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def fetch_html(
    url: str,
    *,
    method: FetchMethod = "requests",
    timeout_s: float = 30.0,
    user_agent: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
) -> Tuple[str, dict]:
    meta = {
        "method": method,
        "url": _clip(url, limit=_META_TEXT_LIMIT),
        "final_url": None,
        "status_code": None,
        "fetched_at": _utcnow_iso(),
        "bytes_len": 0,
        "error": None,
    }

    ua = user_agent or "signalcraft/0.1 (+snapshot-fetch)"
    base_headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        base_headers.update(headers)

    preflight = evaluate_allowlist_policy(url)
    if not preflight.get("final_allowed"):
        meta["error"] = f"egress_blocked:{preflight.get('reason')}"
        meta["final_url"] = _clip(url, limit=_META_TEXT_LIMIT)
        return "", meta

    if method == "requests":
        try:
            result = safe_get_text(
                url,
                headers=base_headers,
                timeout_s=timeout_s,
                max_bytes=_FETCH_MAX_BYTES,
                max_redirects=_FETCH_MAX_REDIRECTS,
            )
            meta["status_code"] = result.status_code
            meta["final_url"] = _clip(result.final_url, limit=_META_TEXT_LIMIT)
            meta["bytes_len"] = result.bytes_len
            return result.text, meta
        except NetworkShieldError as exc:
            meta["error"] = _clip(f"requests error: {exc}", limit=_META_ERROR_LIMIT)
            return "", meta

    if method == "playwright":
        try:
            validate_url_destination(url, allow_schemes=("http", "https"))
        except NetworkShieldError as exc:
            meta["error"] = _clip(f"playwright error: {exc}", limit=_META_ERROR_LIMIT)
            return "", meta

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - import error branch
            raise RuntimeError(
                "Playwright is not installed. Run 'pip install playwright' and 'playwright install chromium'."
            ) from exc

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=ua, viewport={"width": 1280, "height": 720})
                if headers:
                    context.set_extra_http_headers(headers)
                page = context.new_page()
                # Playwright does not expose each redirect hop deterministically in this
                # call path, so we enforce a strict preflight and final URL policy check.
                response = page.goto(url, wait_until="networkidle", timeout=int(timeout_s * 1000))
                html = page.content() or ""
                html_bytes = html.encode("utf-8")
                if len(html_bytes) > _FETCH_MAX_BYTES:
                    raise RuntimeError(f"response exceeds max_bytes={_FETCH_MAX_BYTES}")
                final_url = page.url
                validate_url_destination(final_url, allow_schemes=("http", "https"))
                final_policy = evaluate_allowlist_policy(str(final_url or url))
                if not final_policy.get("final_allowed"):
                    meta["error"] = _clip(
                        f"playwright error: final_url_{final_policy.get('reason')}",
                        limit=_META_ERROR_LIMIT,
                    )
                    context.close()
                    browser.close()
                    return "", meta
                meta["status_code"] = getattr(response, "status", None) if response else None
                meta["final_url"] = _clip(final_url, limit=_META_TEXT_LIMIT)
                meta["bytes_len"] = len(html_bytes)
                context.close()
                browser.close()
                return html, meta
        except Exception as exc:
            meta["error"] = _clip(f"playwright error: {exc}", limit=_META_ERROR_LIMIT)
            return "", meta

    raise RuntimeError(f"Unknown fetch method: {method}")
