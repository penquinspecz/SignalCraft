"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

from typing import Literal, Optional, Tuple

import requests

from ji_engine.providers.retry import evaluate_allowlist_policy
from ji_engine.utils.time import utc_now_z

FetchMethod = Literal["requests", "playwright"]


def _utcnow_iso() -> str:
    return utc_now_z(seconds_precision=True)


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
        "url": url,
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
        meta["final_url"] = url
        return "", meta

    if method == "requests":
        try:
            resp = requests.get(url, headers=base_headers, timeout=timeout_s)
            html = resp.text or ""
            meta["status_code"] = resp.status_code
            meta["final_url"] = str(getattr(resp, "url", url))
            final_policy = evaluate_allowlist_policy(str(meta["final_url"] or url))
            if not final_policy.get("final_allowed"):
                meta["error"] = f"egress_blocked:final_url_{final_policy.get('reason')}"
                return "", meta
            meta["bytes_len"] = len(html.encode("utf-8"))
            return html, meta
        except requests.RequestException as exc:
            meta["error"] = f"requests error: {exc}"
            return "", meta

    if method == "playwright":
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
                meta["status_code"] = getattr(response, "status", None) if response else None
                meta["final_url"] = page.url
                final_policy = evaluate_allowlist_policy(str(meta["final_url"] or url))
                if not final_policy.get("final_allowed"):
                    meta["error"] = f"egress_blocked:final_url_{final_policy.get('reason')}"
                    context.close()
                    browser.close()
                    return "", meta
                meta["bytes_len"] = len(html.encode("utf-8"))
                context.close()
                browser.close()
                return html, meta
        except Exception as exc:
            meta["error"] = f"playwright error: {exc}"
            return "", meta

    raise RuntimeError(f"Unknown fetch method: {method}")
