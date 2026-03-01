"""Tests for Phase2-C7: Egress Shield Enforcement."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ji_engine.providers import retry as provider_retry
from ji_engine.providers.base import BaseJobProvider
from ji_engine.utils.network_shield import NetworkShieldError
from scripts.schema_validate import resolve_named_schema_path, validate_payload


class _TestProvider(BaseJobProvider):
    def scrape_live(self):
        return []

    def load_from_snapshot(self):
        return []


class TestNetworkShieldInFetchPath:
    """Verify network shield is called before any HTTP request."""

    def test_fetch_rejects_private_ip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fetch_text_with_retry must reject requests to private IPs."""
        provider_retry.reset_politeness_state()
        monkeypatch.setenv("JOBINTEL_LIVE_ALLOWLIST_DOMAINS", "*")

        with patch.object(provider_retry.requests, "get") as mock_get:
            with pytest.raises(NetworkShieldError):
                provider_retry.fetch_text_with_retry(
                    "http://127.0.0.1/jobs",
                    max_attempts=2,
                    backoff_base_s=0.0,
                    backoff_max_s=0.0,
                )

        mock_get.assert_not_called()

    def test_fetch_rejects_metadata_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fetch_text_with_retry must reject cloud metadata endpoints."""
        provider_retry.reset_politeness_state()
        monkeypatch.setenv("JOBINTEL_LIVE_ALLOWLIST_DOMAINS", "*")

        with patch.object(provider_retry.requests, "get") as mock_get:
            with pytest.raises(NetworkShieldError):
                provider_retry.fetch_text_with_retry(
                    "http://169.254.169.254/latest/meta-data/",
                    max_attempts=2,
                    backoff_base_s=0.0,
                    backoff_max_s=0.0,
                )

        mock_get.assert_not_called()

    def test_shield_runs_before_retry_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Shield validation must happen before any retry attempt."""
        provider_retry.reset_politeness_state()
        monkeypatch.setenv("JOBINTEL_LIVE_ALLOWLIST_DOMAINS", "*")

        with (
            patch.object(
                provider_retry,
                "validate_url_destination",
                side_effect=NetworkShieldError("blocked for test"),
            ) as mock_validate,
            patch.object(provider_retry.requests, "get") as mock_get,
            patch.object(provider_retry.time, "sleep") as mock_sleep,
        ):
            with pytest.raises(NetworkShieldError, match="blocked for test"):
                provider_retry.fetch_text_with_retry(
                    "https://example.com",
                    max_attempts=3,
                    backoff_base_s=0.0,
                    backoff_max_s=0.0,
                )

        assert mock_validate.call_count == 1
        mock_get.assert_not_called()
        mock_sleep.assert_not_called()


class TestAllowlistFailClosed:
    """Verify allowlist is fail-closed in LIVE/AUTO mode."""

    def test_empty_allowlist_rejects_in_live_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty allowlist must reject all domains in LIVE mode."""
        monkeypatch.setenv("CAREERS_MODE", "LIVE")
        monkeypatch.delenv("JOBINTEL_SCRAPE_MODE", raising=False)
        monkeypatch.delenv("JOBINTEL_LIVE_ALLOWLIST_DOMAINS", raising=False)
        assert provider_retry._allowlist_allows("example.com", []) is False

    def test_empty_allowlist_allows_in_snapshot_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty allowlist is safe in SNAPSHOT mode (no network calls)."""
        monkeypatch.setenv("CAREERS_MODE", "SNAPSHOT")
        monkeypatch.delenv("JOBINTEL_SCRAPE_MODE", raising=False)
        monkeypatch.delenv("JOBINTEL_LIVE_ALLOWLIST_DOMAINS", raising=False)
        assert provider_retry._allowlist_allows("example.com", []) is True


class TestLiveFallbackStructured:
    """Verify LIVE→SNAPSHOT fallback is structured, not silent."""

    def test_security_violation_never_caught(self, tmp_path: Path) -> None:
        """NetworkShieldError must propagate — never fall back to snapshot."""
        provider = _TestProvider(mode="LIVE", data_dir=str(tmp_path))

        with (
            patch.object(provider, "scrape_live", side_effect=NetworkShieldError("blocked")),
            patch.object(provider, "load_from_snapshot", return_value=[]) as mock_snapshot,
        ):
            with pytest.raises(NetworkShieldError):
                provider.fetch_jobs()

        mock_snapshot.assert_not_called()
        assert provider._fallback_triggered is False
        assert provider._fallback_reason is None

    def test_network_error_falls_back_with_metadata(self, tmp_path: Path) -> None:
        """Network errors should fall back but record metadata."""
        provider = _TestProvider(mode="LIVE", data_dir=str(tmp_path))

        with (
            patch.object(provider, "scrape_live", side_effect=ConnectionError("network down")),
            patch.object(provider, "load_from_snapshot", return_value=["snapshot"]) as mock_snapshot,
        ):
            result = provider.fetch_jobs()

        assert result == ["snapshot"]
        mock_snapshot.assert_called_once()
        assert provider._fallback_triggered is True
        assert provider._fallback_reason is not None
        assert "ConnectionError" in provider._fallback_reason

    def test_fallback_metadata_in_run_health(self) -> None:
        """run_health artifact should contain fallback details."""
        schema_path = resolve_named_schema_path("run_health", 1)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = {
            "run_health_schema_version": 1,
            "run_id": "run-test",
            "candidate_id": "local",
            "status": "partial",
            "timestamps": {"started_at": None, "ended_at": None},
            "durations": {"total_sec": 1.2},
            "failed_stage": None,
            "failure_codes": [],
            "phases": {
                "snapshot_fetch": {"status": "success", "duration_sec": 0.1, "failure_codes": []},
                "normalize": {"status": "success", "duration_sec": 0.1, "failure_codes": []},
                "score": {"status": "skipped", "duration_sec": 0.0, "failure_codes": []},
                "publish": {"status": "skipped", "duration_sec": 0.0, "failure_codes": []},
                "ai_sidecar": {"status": "not_run", "duration_sec": 0.0, "failure_codes": []},
            },
            "logs": {},
            "proof_bundle_path": None,
            "fallback_triggered": True,
            "fallback_details": [
                {
                    "provider": "openai",
                    "reason": "ConnectionError: network down",
                    "exception_class": "ConnectionError",
                }
            ],
        }

        assert validate_payload(payload, schema) == []
