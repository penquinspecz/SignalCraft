from __future__ import annotations

from dataclasses import dataclass

import pytest

from ji_engine.utils.network_shield import NetworkShieldError, safe_get_text


@dataclass
class _FakeResponse:
    status_code: int
    chunks: list[bytes]
    url: str
    headers: dict[str, str]
    encoding: str = "utf-8"
    closed: bool = False

    def iter_content(self, chunk_size: int = 8192):
        del chunk_size
        for chunk in self.chunks:
            yield chunk

    def close(self) -> None:
        self.closed = True


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []
        self.trust_env = True
        self.closed = False

    def get(self, url: str, **kwargs):
        del kwargs
        self.calls.append(url)
        if not self._responses:
            raise AssertionError("unexpected request")
        return self._responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_safe_get_text_blocks_redirect_to_loopback(monkeypatch) -> None:
    session = _FakeSession(
        responses=[
            _FakeResponse(
                status_code=302,
                chunks=[],
                url="https://93.184.216.34/",
                headers={"Location": "http://127.0.0.1/private"},
            )
        ]
    )
    monkeypatch.setattr("ji_engine.utils.network_shield.requests.Session", lambda: session)

    with pytest.raises(NetworkShieldError, match="blocked ip"):
        safe_get_text(
            "https://93.184.216.34/",
            headers={"User-Agent": "signalcraft-test"},
            timeout_s=5,
            max_bytes=4096,
            max_redirects=5,
        )

    assert session.calls == ["https://93.184.216.34/"]


def test_safe_get_text_enforces_max_bytes(monkeypatch) -> None:
    session = _FakeSession(
        responses=[
            _FakeResponse(
                status_code=200,
                chunks=[b"abcdef", b"ghijkl"],
                url="https://93.184.216.34/",
                headers={},
            )
        ]
    )
    monkeypatch.setattr("ji_engine.utils.network_shield.requests.Session", lambda: session)

    with pytest.raises(NetworkShieldError, match="max_bytes"):
        safe_get_text(
            "https://93.184.216.34/",
            headers={"User-Agent": "signalcraft-test"},
            timeout_s=5,
            max_bytes=10,
            max_redirects=5,
        )

    assert session.calls == ["https://93.184.216.34/"]
