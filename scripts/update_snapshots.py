#!/usr/bin/env python3
from __future__ import annotations

try:
    import _bootstrap  # type: ignore
except ModuleNotFoundError:
    from scripts import _bootstrap  # noqa: F401

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ji_engine.providers.openai_provider import CAREERS_SEARCH_URL
from ji_engine.providers.registry import load_providers_config
from ji_engine.utils.job_id import extract_job_id_from_url


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        return _sha256_bytes(path.read_bytes())
    except Exception:
        return None


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _meta_path(out_dir: Path) -> Path:
    return out_dir / "index.meta.json"


def _build_meta(
    *,
    provider: str,
    url: str,
    http_status: Optional[int],
    bytes_count: int,
    sha256: Optional[str],
    note: Optional[str],
) -> dict:
    return {
        "fetched_at": _utcnow_iso(),
        "url": url,
        "http_status": http_status,
        "bytes": bytes_count,
        "sha256": sha256,
        "provider": provider,
        "note": note,
    }


def _write_meta(out_dir: Path, payload: dict) -> None:
    _atomic_write(_meta_path(out_dir), json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))


def _fetch_html(url: str, timeout: float, user_agent: str) -> Tuple[Optional[bytes], Optional[int], Optional[str]]:
    req = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return data, getattr(resp, "status", 200), None
    except HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = None
        return body, e.code, f"HTTPError: {e}"
    except URLError as e:
        return None, None, f"URLError: {e}"


def _fetch_with_retry(
    url: str,
    timeout: float,
    user_agent: str,
    retries: int,
    sleep_s: float,
) -> Tuple[Optional[bytes], Optional[int], Optional[str]]:
    last_data: Optional[bytes] = None
    last_status: Optional[int] = None
    last_error: Optional[str] = None
    for attempt in range(retries + 1):
        data, status, error = _fetch_html(url, timeout, user_agent)
        if status == 200 and data:
            return data, status, None
        last_data, last_status, last_error = data, status, error
        if attempt < retries:
            time.sleep(sleep_s)
    return last_data, last_status, last_error


def _extract_apply_urls(html: str) -> list[str]:
    pattern = re.compile(r'"applyUrl"\s*:\s*"([^"]+)"')
    seen: set[str] = set()
    urls: list[str] = []
    for match in pattern.finditer(html):
        url = html_lib.unescape(match.group(1))
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _load_apply_urls_from_jobs_json(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        url = item.get("apply_url")
        if isinstance(url, str) and url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _limit_apply_urls(urls: Iterable[str], max_jobs: Optional[int]) -> list[str]:
    if max_jobs is None:
        return list(urls)
    limited: list[str] = []
    for url in urls:
        if len(limited) >= max_jobs:
            break
        limited.append(url)
    return limited


def _snapshot_openai_jobs(
    html: str,
    out_dir: Path,
    timeout: float,
    user_agent: str,
    apply_urls: Optional[list[str]] = None,
    max_jobs: Optional[int] = None,
    max_workers: int = 4,
    retries: int = 2,
    sleep_s: float = 0.5,
) -> None:
    if apply_urls is None:
        apply_urls = _extract_apply_urls(html)
    apply_urls = _limit_apply_urls(apply_urls, max_jobs)
    if not apply_urls:
        print("No apply URLs found; skipping job detail snapshots.")
        return

    jobs_dir = out_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    def _fetch_one(url: str) -> Tuple[str, Optional[str], Optional[str]]:
        job_id = extract_job_id_from_url(url) or ""
        if not job_id:
            return url, None, "missing_job_id"
        data, status, error = _fetch_with_retry(url, timeout, user_agent, retries, sleep_s)
        if status != 200 or not data:
            return url, job_id, error or f"HTTP status {status}"
        html_text = data.decode("utf-8", errors="ignore")
        if "<html" not in html_text.lower() and "<!doctype" not in html_text.lower():
            return url, job_id, "non_html_response"
        _atomic_write(jobs_dir / f"{job_id}.html", data)
        return url, job_id, None

    failures = 0
    successes = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for _url, job_id, error in pool.map(_fetch_one, apply_urls):
            if error:
                failures += 1
                print(f"Job snapshot failed ({job_id or 'unknown'}): {error}")
            else:
                successes += 1
                print(f"Job snapshot saved: {job_id}")

    total = len(apply_urls)
    print(f"Job detail snapshots complete. total={total} ok={successes} failed={failures}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", help="Single provider id (legacy)")
    ap.add_argument(
        "--providers",
        action="append",
        help="Comma-separated provider ids (repeatable). Overrides --provider when set.",
    )
    ap.add_argument("--url")
    ap.add_argument("--out_dir")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--user_agent", default="job-intelligence-engine/0.1")
    ap.add_argument("--jobs_json", help="OpenAI jobs JSON to source apply_url values from.")
    ap.add_argument("--max_jobs", type=int, default=None, help="Limit job detail snapshots.")
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument(
        "--providers_config",
        default=str(Path("config") / "providers.json"),
        help="Path to providers config JSON.",
    )
    args = ap.parse_args(argv)

    providers_arg = args.providers
    if providers_arg:
        providers_list: list[str] = []
        for item in providers_arg:
            providers_list.extend([p.strip() for p in item.split(",") if p.strip()])
    else:
        providers_list = [args.provider.strip()] if args.provider else []

    if not providers_list:
        raise SystemExit("Must provide --provider or --providers.")

    providers_cfg = load_providers_config(Path(args.providers_config))
    provider_map = {p["provider_id"]: p for p in providers_cfg}

    exit_code = 0
    for provider in providers_list:
        provider = provider.lower().strip()
        if provider not in provider_map and provider != "openai":
            raise SystemExit(f"Unknown provider '{provider}'.")

        provider_cfg = provider_map.get(provider)
        url = args.url or (provider_cfg.get("board_url") if provider_cfg else None) or CAREERS_SEARCH_URL
        out_dir = Path(
            args.out_dir
            or (provider_cfg.get("snapshot_dir") if provider_cfg else None)
            or str(Path("data") / f"{provider}_snapshots")
        )
        html_path = out_dir / "index.html"

        data, status, error = _fetch_html(url, args.timeout, args.user_agent)
        ok = status == 200 and data is not None
        note = None
        if not ok:
            note = error or f"HTTP status {status}"
        if not ok and not args.force:
            if not args.dry_run:
                payload = _build_meta(
                    provider=provider,
                    url=url,
                    http_status=status,
                    bytes_count=len(data or b""),
                    sha256=_sha256_file(html_path),
                    note=note,
                )
                _write_meta(out_dir, payload)
            exit_code = max(exit_code, 1)
            continue

        if args.dry_run:
            exit_code = max(exit_code, 0 if ok else 1)
            continue

        if data is not None:
            _atomic_write(html_path, data)
        else:
            print("Warning: no HTML content fetched; leaving existing index.html untouched.")
        sha256 = _sha256_file(html_path)
        payload = _build_meta(
            provider=provider,
            url=url,
            http_status=status,
            bytes_count=len(data or b""),
            sha256=sha256,
            note=note,
        )
        _write_meta(out_dir, payload)
        if provider == "openai":
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
            jobs_json_path: Optional[Path] = Path(args.jobs_json) if args.jobs_json else None
            if jobs_json_path is None:
                labeled_path = out_dir.parent / "openai_labeled_jobs.json"
                raw_path = out_dir.parent / "openai_raw_jobs.json"
                if labeled_path.exists():
                    jobs_json_path = labeled_path
                elif raw_path.exists():
                    jobs_json_path = raw_path

            apply_urls: Optional[list[str]] = None
            if jobs_json_path is not None:
                apply_urls = _load_apply_urls_from_jobs_json(jobs_json_path)

            if html_text or apply_urls:
                _snapshot_openai_jobs(
                    html_text,
                    out_dir,
                    timeout=args.timeout,
                    user_agent=args.user_agent,
                    apply_urls=apply_urls,
                    max_jobs=args.max_jobs,
                )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
