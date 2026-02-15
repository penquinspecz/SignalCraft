from __future__ import annotations

from types import SimpleNamespace

import pytest

from ji_engine.providers import retry as provider_retry
from jobintel.snapshots.fetch import fetch_html
from scripts import update_snapshots


def _set_allowlist(monkeypatch: pytest.MonkeyPatch, entries: str) -> None:
    monkeypatch.setenv("JOBINTEL_LIVE_ALLOWLIST_DOMAINS", entries)


@pytest.mark.parametrize(
    ("fn_name", "url", "network_attr"),
    [
        ("fetch_text_with_retry", "https://blocked.example/path", "get"),
        ("fetch_json_with_retry", "https://blocked.example/path", "post"),
    ],
)
def test_retry_requests_fetch_methods_fail_closed_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    fn_name: str,
    url: str,
    network_attr: str,
) -> None:
    provider_retry.reset_politeness_state()
    _set_allowlist(monkeypatch, "allowed.example")
    calls = {"count": 0}

    def _network_call(*_args, **_kwargs):
        calls["count"] += 1
        raise AssertionError("network call should be blocked by allowlist preflight")

    monkeypatch.setattr(provider_retry.requests, network_attr, _network_call)

    with pytest.raises(provider_retry.ProviderFetchError) as exc:
        fn = getattr(provider_retry, fn_name)
        fn(url, max_attempts=1, backoff_base_s=0.0, backoff_max_s=0.0)

    assert exc.value.reason == "allowlist_denied"
    assert calls["count"] == 0


def test_retry_urlopen_fetch_method_fail_closed_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    provider_retry.reset_politeness_state()
    _set_allowlist(monkeypatch, "allowed.example")
    calls = {"count": 0}

    def _urlopen(*_args, **_kwargs):
        calls["count"] += 1
        raise AssertionError("urlopen should be blocked by allowlist preflight")

    monkeypatch.setattr(provider_retry, "urlopen", _urlopen)

    with pytest.raises(provider_retry.ProviderFetchError) as exc:
        provider_retry.fetch_urlopen_with_retry(
            "https://blocked.example/path",
            max_attempts=1,
            backoff_base_s=0.0,
            backoff_max_s=0.0,
        )

    assert exc.value.reason == "allowlist_denied"
    assert calls["count"] == 0


def test_retry_final_url_allowlist_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    provider_retry.reset_politeness_state()
    _set_allowlist(monkeypatch, "allowed.example")
    monkeypatch.setenv("JOBINTEL_PROVIDER_MIN_DELAY_S", "0")
    monkeypatch.setenv("JOBINTEL_PROVIDER_BACKOFF_JITTER_S", "0")
    monkeypatch.setattr(
        provider_retry.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200,
            text="<html>ok</html>",
            url="https://blocked.example/redirected",
        ),
    )

    with pytest.raises(provider_retry.ProviderFetchError) as exc:
        provider_retry.fetch_text_with_retry(
            "https://allowed.example/path",
            max_attempts=1,
            backoff_base_s=0.0,
            backoff_max_s=0.0,
        )

    assert exc.value.reason == "allowlist_denied"


def test_snapshot_fetch_requests_validates_final_url_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_allowlist(monkeypatch, "allowed.example")
    monkeypatch.setattr(
        "jobintel.snapshots.fetch.requests.get",
        lambda *_args, **_kwargs: SimpleNamespace(
            text="<html>ok</html>",
            status_code=200,
            url="https://blocked.example/final",
        ),
    )

    html, meta = fetch_html("https://allowed.example/start", method="requests", timeout_s=5)
    assert html == ""
    assert str(meta["error"]).startswith("egress_blocked:final_url_allowlist_denied")


def test_snapshot_fetch_playwright_preflight_blocks_before_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_allowlist(monkeypatch, "allowed.example")
    html, meta = fetch_html("https://blocked.example/start", method="playwright", timeout_s=5)
    assert html == ""
    assert str(meta["error"]).startswith("egress_blocked:allowlist_denied")


def test_update_snapshots_urlopen_fail_closed_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_allowlist(monkeypatch, "allowed.example")
    calls = {"count": 0}

    def _urlopen(*_args, **_kwargs):
        calls["count"] += 1
        raise AssertionError("urlopen should not run when preflight blocks")

    monkeypatch.setattr(update_snapshots, "urlopen", _urlopen)
    data, status, error = update_snapshots._fetch_html("https://blocked.example/index.html", 1.0, "signalcraft-test")
    assert data is None
    assert status is None
    assert str(error).startswith("egress_blocked:allowlist_denied")
    assert calls["count"] == 0
