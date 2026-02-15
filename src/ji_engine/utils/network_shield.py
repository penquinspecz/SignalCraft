"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from urllib.parse import urljoin, urlparse

import requests

_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_ERROR_CHARS = 240
IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class NetworkShieldError(RuntimeError):
    """Fail-closed error for blocked or unsafe outbound fetches."""


@dataclass(frozen=True)
class SafeGetResult:
    text: str
    status_code: Optional[int]
    final_url: str
    bytes_len: int


def _clip(text: str, *, limit: int = _MAX_ERROR_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _blocked_ip_reason(ip: IPAddress) -> Optional[str]:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _blocked_ip_reason(mapped)
    if ip.is_loopback:
        return "loopback"
    if ip.is_private:
        return "private"
    if ip.is_link_local:
        return "link-local"
    if ip.is_multicast:
        return "multicast"
    if ip.is_reserved:
        return "reserved"
    if ip.is_unspecified:
        return "unspecified"
    if isinstance(ip, ipaddress.IPv6Address) and ip.is_site_local:
        return "site-local"
    return None


def _iter_resolved_ips(hostname: str, port: int) -> Iterable[IPAddress]:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise NetworkShieldError(f"dns resolution failed for host={hostname}") from exc

    if not infos:
        raise NetworkShieldError(f"dns resolution returned no records for host={hostname}")

    seen: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_text = str(sockaddr[0])
        if ip_text in seen:
            continue
        seen.add(ip_text)
        try:
            yield ipaddress.ip_address(ip_text)
        except ValueError as exc:
            raise NetworkShieldError(f"invalid ip resolved for host={hostname}") from exc


def _matches_domain(host: str, domain: str) -> bool:
    domain = domain.lstrip(".")
    return host == domain or host.endswith(f".{domain}")


def validate_url_destination(
    url: str,
    *,
    allow_schemes: Sequence[str] = ("http", "https"),
    allow_hosts: Optional[Sequence[str]] = None,
    allow_domains: Optional[Sequence[str]] = None,
) -> None:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    allowed_schemes = tuple(s.lower() for s in allow_schemes)
    if scheme not in allowed_schemes:
        raise NetworkShieldError(f"scheme not allowed: {scheme or 'missing'}")
    if parsed.username or parsed.password:
        raise NetworkShieldError("credentials in url are not allowed")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise NetworkShieldError("url host is missing")
    if host == "localhost":
        raise NetworkShieldError("blocked host: localhost")

    allowed_hosts = {h.strip().lower() for h in allow_hosts or () if h and h.strip()}
    if allowed_hosts and host not in allowed_hosts:
        raise NetworkShieldError("host not in allow_hosts policy")

    allowed_domains = [d.strip().lower() for d in allow_domains or () if d and d.strip()]
    if allowed_domains and not any(_matches_domain(host, d) for d in allowed_domains):
        raise NetworkShieldError("host not in allow_domains policy")

    ip: Optional[IPAddress]
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is None:
        port = parsed.port or (443 if scheme == "https" else 80)
        for resolved_ip in _iter_resolved_ips(host, port):
            reason = _blocked_ip_reason(resolved_ip)
            if reason:
                raise NetworkShieldError(f"blocked ip via dns: {resolved_ip} ({reason})")
        return

    reason = _blocked_ip_reason(ip)
    if reason:
        raise NetworkShieldError(f"blocked ip: {ip} ({reason})")


def _read_limited_bytes(response: requests.Response, *, max_bytes: int) -> bytes:
    payload = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            if len(payload) + len(chunk) > max_bytes:
                raise NetworkShieldError(f"response exceeds max_bytes={max_bytes}")
            payload.extend(chunk)
    except requests.RequestException as exc:
        raise NetworkShieldError(f"stream read failed: {_clip(str(exc))}") from exc
    return bytes(payload)


def safe_get_text(
    url: str,
    *,
    headers: Optional[dict[str, str]],
    timeout_s: float,
    max_bytes: int,
    allow_schemes: Sequence[str] = ("http", "https"),
    max_redirects: int = 5,
    allow_hosts: Optional[Sequence[str]] = None,
    allow_domains: Optional[Sequence[str]] = None,
) -> SafeGetResult:
    if timeout_s <= 0 or timeout_s > 120:
        raise NetworkShieldError("timeout_s must be in (0, 120]")
    if max_bytes <= 0:
        raise NetworkShieldError("max_bytes must be > 0")
    if max_redirects < 0:
        raise NetworkShieldError("max_redirects must be >= 0")

    req_headers = dict(headers or {})
    current_url = url
    redirects = 0
    session = requests.Session()
    session.trust_env = False
    try:
        while True:
            validate_url_destination(
                current_url,
                allow_schemes=allow_schemes,
                allow_hosts=allow_hosts,
                allow_domains=allow_domains,
            )
            response: Optional[requests.Response] = None
            try:
                response = session.get(
                    current_url,
                    headers=req_headers,
                    timeout=timeout_s,
                    allow_redirects=False,
                    stream=True,
                )
                status_code = int(getattr(response, "status_code", 0) or 0)
                location = response.headers.get("Location") if getattr(response, "headers", None) else None
                if status_code in _REDIRECT_STATUS_CODES and location:
                    redirects += 1
                    if redirects > max_redirects:
                        raise NetworkShieldError(f"max_redirects exceeded: {max_redirects}")
                    next_url = urljoin(current_url, location)
                    validate_url_destination(
                        next_url,
                        allow_schemes=allow_schemes,
                        allow_hosts=allow_hosts,
                        allow_domains=allow_domains,
                    )
                    current_url = next_url
                    continue

                final_url = str(getattr(response, "url", current_url) or current_url)
                validate_url_destination(
                    final_url,
                    allow_schemes=allow_schemes,
                    allow_hosts=allow_hosts,
                    allow_domains=allow_domains,
                )
                payload = _read_limited_bytes(response, max_bytes=max_bytes)
                encoding = (getattr(response, "encoding", None) or "utf-8").strip() or "utf-8"
                return SafeGetResult(
                    text=payload.decode(encoding, errors="replace"),
                    status_code=status_code,
                    final_url=final_url,
                    bytes_len=len(payload),
                )
            except requests.RequestException as exc:
                raise NetworkShieldError(f"requests transport error: {_clip(str(exc))}") from exc
            finally:
                if response is not None:
                    response.close()
    finally:
        session.close()
