from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.scrape import router as scrape_router
from app.core.db import get_db
from app.core.dependencies import require_api_key


def _build_scrape_client() -> TestClient:
    app = FastAPI()
    app.include_router(scrape_router, prefix="/api/v1")
    app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_db] = lambda: object()
    return TestClient(app)


def test_clear_failed_requires_explicit_confirmation() -> None:
    client = _build_scrape_client()

    response = client.post("/api/v1/scrape/clear-failed", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing confirmation. Set confirm=true to proceed with deletion."


def test_truncate_all_requires_explicit_confirmation() -> None:
    client = _build_scrape_client()

    response = client.post("/api/v1/scrape/truncate-all", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Missing confirmation. Set confirm=true to proceed with deletion. This is a destructive operation!"
    )
