from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import prometheus


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(prometheus.router)
    return TestClient(app)


def test_metrics_endpoint_returns_prometheus_payload_and_cache_headers() -> None:
    client = _build_client()
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    assert "text/plain" in response.headers["content-type"]
    assert response.text


def test_metrics_endpoint_when_generator_fails_then_returns_500_fallback(monkeypatch) -> None:
    def _raise_error(_registry):
        raise RuntimeError("metrics failure")

    monkeypatch.setattr(prometheus, "generate_latest", _raise_error)

    client = _build_client()
    response = client.get("/metrics")

    assert response.status_code == 500
    assert response.text == "# Error generating metrics\n"
    assert "text/plain" in response.headers["content-type"]


def test_metrics_health_endpoint_returns_expected_contract() -> None:
    client = _build_client()
    response = client.get("/metrics/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "prometheus-metrics",
        "registry": "quark_strm",
    }
