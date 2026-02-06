"""
Emby refresh integration API tests
"""

from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_emby_status_endpoint():
    resp = client.get("/api/emby/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "connected" in data
    assert "configuration" in data
    assert "episode_aggregate_window_seconds" in data["configuration"]
    assert "delete_execute_enabled" in data["configuration"]


def test_emby_test_connection_endpoint():
    resp = client.post("/api/emby/test-connection", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data


def test_emby_libraries_requires_enabled():
    resp = client.get("/api/emby/libraries")
    assert resp.status_code in (400, 500)


def test_emby_refresh_requires_enabled():
    resp = client.post("/api/emby/refresh", json={})
    assert resp.status_code in (400, 500)
