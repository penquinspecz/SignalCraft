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

import certifi
import urllib3

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


@dataclass(frozen=True)
class _ResolvedRequestHop:
    normalized_url: str
    scheme: str
    host: str
    port: int
    host_header: str
    connect_ip: IPAddress
    request_target: str


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


def _is_default_port(*, scheme: str, port: int) -> bool:
    return (scheme == "http" and port == 80) or (scheme == "https" and port == 443)


def _format_authority_host(host: str) -> str:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(ip, ipaddress.IPv6Address):
        return f"[{host}]"
    return host


def _build_request_target(parsed) -> str:
    path = parsed.path or "/"
    if parsed.params:
        path = f"{path};{parsed.params}"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _resolve_request_hop(
    url: str,
    *,
    allow_schemes: Sequence[str] = ("http", "https"),
    allow_hosts: Optional[Sequence[str]] = None,
    allow_domains: Optional[Sequence[str]] = None,
) -> _ResolvedRequestHop:
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

    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise NetworkShieldError("invalid url port") from exc
    port = parsed_port or (443 if scheme == "https" else 80)

    ip: Optional[IPAddress]
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is None:
        connect_ip: Optional[IPAddress] = None
        for resolved_ip in _iter_resolved_ips(host, port):
            reason = _blocked_ip_reason(resolved_ip)
            if reason:
                raise NetworkShieldError(f"blocked ip via dns: {resolved_ip} ({reason})")
            if connect_ip is None:
                connect_ip = resolved_ip
        if connect_ip is None:
            raise NetworkShieldError(f"dns resolution returned no records for host={host}")
    else:
        reason = _blocked_ip_reason(ip)
        if reason:
            raise NetworkShieldError(f"blocked ip: {ip} ({reason})")
        connect_ip = ip

    authority_host = _format_authority_host(host)
    if parsed_port is None or _is_default_port(scheme=scheme, port=parsed_port):
        host_header = authority_host
    else:
        host_header = f"{authority_host}:{parsed_port}"

    normalized_url = parsed._replace(fragment="").geturl()
    return _ResolvedRequestHop(
        normalized_url=normalized_url,
        scheme=scheme,
        host=host,
        port=port,
        host_header=host_header,
        connect_ip=connect_ip,
        request_target=_build_request_target(parsed),
    )


def validate_url_destination(
    url: str,
    *,
    allow_schemes: Sequence[str] = ("http", "https"),
    allow_hosts: Optional[Sequence[str]] = None,
    allow_domains: Optional[Sequence[str]] = None,
) -> None:
    _resolve_request_hop(
        url,
        allow_schemes=allow_schemes,
        allow_hosts=allow_hosts,
        allow_domains=allow_domains,
    )


def _read_limited_bytes(response: urllib3.response.BaseHTTPResponse, *, max_bytes: int) -> bytes:
    payload = bytearray()
    try:
        for chunk in response.stream(amt=8192, decode_content=True):
            if not chunk:
                continue
            if len(payload) + len(chunk) > max_bytes:
                raise NetworkShieldError(f"response exceeds max_bytes={max_bytes}")
            payload.extend(chunk)
    except urllib3.exceptions.HTTPError as exc:
        raise NetworkShieldError(f"stream read failed: {_clip(str(exc))}") from exc
    return bytes(payload)


def _response_encoding(response: urllib3.response.BaseHTTPResponse) -> str:
    content_type = str(response.headers.get("Content-Type") or "")
    for part in content_type.split(";")[1:]:
        key, sep, value = part.strip().partition("=")
        if sep and key.lower() == "charset":
            encoding = value.strip().strip("\"'")
            if encoding:
                return encoding
    return "utf-8"


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
    pool_manager = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where(), retries=False)
    try:
        while True:
            hop = _resolve_request_hop(
                current_url,
                allow_schemes=allow_schemes,
                allow_hosts=allow_hosts,
                allow_domains=allow_domains,
            )
            current_url = hop.normalized_url
            response: Optional[urllib3.response.BaseHTTPResponse] = None
            try:
                pool_kwargs = None
                if hop.scheme == "https":
                    # Connect to the pinned IP while keeping Host/SNI + cert checks on the origin hostname.
                    pool_kwargs = {"assert_hostname": hop.host, "server_hostname": hop.host}
                pool = pool_manager.connection_from_host(
                    host=str(hop.connect_ip),
                    port=hop.port,
                    scheme=hop.scheme,
                    pool_kwargs=pool_kwargs,
                )
                request_headers = dict(req_headers)
                request_headers["Host"] = hop.host_header
                response = pool.urlopen(
                    method="GET",
                    url=hop.request_target,
                    headers=request_headers,
                    redirect=False,
                    retries=False,
                    assert_same_host=False,
                    timeout=urllib3.Timeout(connect=timeout_s, read=timeout_s),
                    preload_content=False,
                )
                status_code = int(getattr(response, "status", 0) or 0)
                location = response.headers.get("Location") if getattr(response, "headers", None) else None
                if status_code in _REDIRECT_STATUS_CODES and location:
                    redirects += 1
                    if redirects > max_redirects:
                        raise NetworkShieldError(f"max_redirects exceeded: {max_redirects}")
                    next_url = urljoin(current_url, location)
                    current_url = next_url
                    continue

                payload = _read_limited_bytes(response, max_bytes=max_bytes)
                encoding = _response_encoding(response)
                return SafeGetResult(
                    text=payload.decode(encoding, errors="replace"),
                    status_code=status_code,
                    final_url=current_url,
                    bytes_len=len(payload),
                )
            except urllib3.exceptions.HTTPError as exc:
                raise NetworkShieldError(f"requests transport error: {_clip(str(exc))}") from exc
            finally:
                if response is not None:
                    response.close()
    finally:
        pool_manager.clear()
