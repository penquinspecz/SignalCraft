from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Optional

import pytest

from ji_engine.utils.network_shield import NetworkShieldError, safe_get_text


@dataclass
class _FakeResponse:
    status: int
    chunks: list[bytes]
    headers: dict[str, str]
    closed: bool = False

    def stream(self, amt: int = 8192, decode_content: bool = True):
        del amt, decode_content
        for chunk in self.chunks:
            yield chunk

    def close(self) -> None:
        self.closed = True


class _FakePool:
    def __init__(
        self,
        *,
        responses: list[_FakeResponse],
        urlopen_calls: list[dict],
    ) -> None:
        self._responses = responses
        self._urlopen_calls = urlopen_calls

    def urlopen(self, *, method: str, url: str, headers: dict[str, str], **kwargs):
        call = {"method": method, "url": url, "headers": dict(headers), "kwargs": dict(kwargs)}
        self._urlopen_calls.append(call)
        if not self._responses:
            raise AssertionError("unexpected request")
        return self._responses.pop(0)


class _FakePoolManager:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.connection_calls: list[dict] = []
        self.urlopen_calls: list[dict] = []
        self.cleared = False

    def connection_from_host(
        self,
        host: str,
        *,
        port: Optional[int] = None,
        scheme: Optional[str] = None,
        pool_kwargs: Optional[dict] = None,
    ) -> _FakePool:
        self.connection_calls.append(
            {
                "host": host,
                "port": port,
                "scheme": scheme,
                "pool_kwargs": dict(pool_kwargs or {}),
            }
        )
        return _FakePool(responses=self._responses, urlopen_calls=self.urlopen_calls)

    def clear(self) -> None:
        self.cleared = True


def _patch_pool_manager(monkeypatch: pytest.MonkeyPatch, responses: list[_FakeResponse]) -> _FakePoolManager:
    manager = _FakePoolManager(responses)
    monkeypatch.setattr("ji_engine.utils.network_shield.urllib3.PoolManager", lambda **_kwargs: manager)
    return manager


def _gaia_records(ip: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, 443))]


def test_safe_get_text_blocks_redirect_to_loopback(monkeypatch) -> None:
    manager = _patch_pool_manager(
        monkeypatch,
        responses=[
            _FakeResponse(
                status=302,
                chunks=[],
                headers={"Location": "http://127.0.0.1/private"},
            )
        ],
    )

    with pytest.raises(NetworkShieldError, match="blocked ip"):
        safe_get_text(
            "https://93.184.216.34/",
            headers={"User-Agent": "signalcraft-test"},
            timeout_s=5,
            max_bytes=4096,
            max_redirects=5,
        )

    assert manager.connection_calls == [
        {
            "host": "93.184.216.34",
            "port": 443,
            "scheme": "https",
            "pool_kwargs": {"assert_hostname": "93.184.216.34", "server_hostname": "93.184.216.34"},
        }
    ]


def test_safe_get_text_enforces_max_bytes(monkeypatch) -> None:
    manager = _patch_pool_manager(
        monkeypatch,
        responses=[
            _FakeResponse(
                status=200,
                chunks=[b"abcdef", b"ghijkl"],
                headers={},
            )
        ],
    )

    with pytest.raises(NetworkShieldError, match="max_bytes"):
        safe_get_text(
            "https://93.184.216.34/",
            headers={"User-Agent": "signalcraft-test"},
            timeout_s=5,
            max_bytes=10,
            max_redirects=5,
        )

    assert [c["host"] for c in manager.connection_calls] == ["93.184.216.34"]


def test_safe_get_text_pins_https_hop_to_resolved_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _patch_pool_manager(
        monkeypatch,
        responses=[_FakeResponse(status=200, chunks=[b"ok"], headers={"Content-Type": "text/plain; charset=utf-8"})],
    )

    def _safe_dns(hostname: str, port: int, *, type: int, proto: int):
        del port, type, proto
        assert hostname == "safe.example"
        return _gaia_records("93.184.216.34")

    monkeypatch.setattr("ji_engine.utils.network_shield.socket.getaddrinfo", _safe_dns)

    result = safe_get_text(
        "https://safe.example/path?a=1",
        headers={"User-Agent": "signalcraft-test"},
        timeout_s=5,
        max_bytes=4096,
        max_redirects=5,
    )

    assert result.text == "ok"
    assert result.status_code == 200
    assert result.final_url == "https://safe.example/path?a=1"
    assert manager.connection_calls == [
        {
            "host": "93.184.216.34",
            "port": 443,
            "scheme": "https",
            "pool_kwargs": {"assert_hostname": "safe.example", "server_hostname": "safe.example"},
        }
    ]
    assert len(manager.urlopen_calls) == 1
    call = manager.urlopen_calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "/path?a=1"
    assert call["headers"] == {"User-Agent": "signalcraft-test", "Host": "safe.example"}
    assert call["kwargs"]["redirect"] is False
    assert call["kwargs"]["retries"] is False
    assert call["kwargs"]["assert_same_host"] is False
    assert call["kwargs"]["preload_content"] is False
    assert call["kwargs"]["timeout"] is not None


def test_safe_get_text_blocks_rebinding_on_redirect_hop(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _patch_pool_manager(
        monkeypatch,
        responses=[_FakeResponse(status=302, chunks=[], headers={"Location": "/next"})],
    )
    calls = {"count": 0}

    def _rebind_dns(hostname: str, port: int, *, type: int, proto: int):
        del port, type, proto
        if hostname != "rebind.example":
            raise AssertionError(f"unexpected host lookup: {hostname}")
        calls["count"] += 1
        if calls["count"] == 1:
            return _gaia_records("93.184.216.34")
        return _gaia_records("127.0.0.1")

    monkeypatch.setattr("ji_engine.utils.network_shield.socket.getaddrinfo", _rebind_dns)

    with pytest.raises(NetworkShieldError, match="blocked ip via dns: 127.0.0.1"):
        safe_get_text(
            "https://rebind.example/start",
            headers={"User-Agent": "signalcraft-test"},
            timeout_s=5,
            max_bytes=4096,
            max_redirects=5,
        )

    assert calls["count"] == 2
    assert len(manager.connection_calls) == 1
