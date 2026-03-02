from __future__ import annotations

import importlib
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def _reload_dashboard(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    import ji_engine.config as config
    import ji_engine.dashboard.app as dashboard

    importlib.reload(config)
    return importlib.reload(dashboard)


class TestDashboardBinding:
    def test_default_host_is_localhost(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DASHBOARD_HOST", raising=False)
        monkeypatch.delenv("DASHBOARD_PORT", raising=False)
        monkeypatch.delenv("DASHBOARD_AUTH_ENABLED", raising=False)
        monkeypatch.delenv("DASHBOARD_AUTH_TOKEN", raising=False)
        dashboard = _reload_dashboard(tmp_path, monkeypatch)
        assert dashboard.DASHBOARD_HOST == "127.0.0.1"
        assert dashboard.DASHBOARD_PORT == 8080


class TestDashboardAuthMiddleware:
    def test_auth_disabled_by_default(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DASHBOARD_AUTH_ENABLED", raising=False)
        monkeypatch.delenv("DASHBOARD_AUTH_TOKEN", raising=False)
        dashboard = _reload_dashboard(tmp_path, monkeypatch)
        client = TestClient(dashboard.app)

        resp = client.get("/runs")
        assert resp.status_code == 200

    def test_auth_enabled_requires_token(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DASHBOARD_AUTH_ENABLED", "true")
        monkeypatch.setenv("DASHBOARD_AUTH_TOKEN", "test-token")
        dashboard = _reload_dashboard(tmp_path, monkeypatch)
        client = TestClient(dashboard.app)

        resp = client.get("/runs")
        assert resp.status_code == 401
        assert resp.json()["error"] == "Authorization required"

    def test_auth_enabled_accepts_valid_token(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DASHBOARD_AUTH_ENABLED", "true")
        monkeypatch.setenv("DASHBOARD_AUTH_TOKEN", "test-token")
        dashboard = _reload_dashboard(tmp_path, monkeypatch)
        client = TestClient(dashboard.app)

        resp = client.get("/runs", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200

    def test_auth_enabled_rejects_invalid_token(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DASHBOARD_AUTH_ENABLED", "true")
        monkeypatch.setenv("DASHBOARD_AUTH_TOKEN", "test-token")
        dashboard = _reload_dashboard(tmp_path, monkeypatch)
        client = TestClient(dashboard.app)

        resp = client.get("/runs", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 403
        assert resp.json()["error"] == "Invalid token"

    def test_health_endpoint_skips_auth(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DASHBOARD_AUTH_ENABLED", "true")
        monkeypatch.setenv("DASHBOARD_AUTH_TOKEN", "test-token")
        dashboard = _reload_dashboard(tmp_path, monkeypatch)
        client = TestClient(dashboard.app)

        resp = client.get("/version")
        assert resp.status_code == 200
