"""
Sensitive endpoint auth guard tests.
"""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_sensitive_endpoints_require_api_key_when_configured(monkeypatch):
    api_key = "unit-test-api-key"
    monkeypatch.setenv("SMART_MEDIA_API_KEY", api_key)

    targets = [
        "/api/proxy/cache/stats",
        "/api/notification/channels",
        "/config",
    ]

    for path in targets:
        unauthorized = client.get(path)
        assert unauthorized.status_code == 401

        authorized = client.get(path, headers={"X-API-Key": api_key})
        assert authorized.status_code not in {401, 403}
