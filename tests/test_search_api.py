from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import search as search_api
from app.core import sdk_config as sdk_config_module


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(search_api.router)
    return TestClient(app)


def test_search_resources_success_passes_fixed_params(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeService:
        async def search(self, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {"items": [{"id": 1}], "total": 1}

    monkeypatch.setattr(search_api, "ResourceSearchService", FakeService)

    response = client.get("/api/search", params={"keyword": "movie", "page": 2, "page_size": 15})

    assert response.status_code == 200
    assert response.json() == {"items": [{"id": 1}], "total": 1}
    assert captured == {
        "keyword": "movie",
        "cloud_types": ["quark"],
        "page": 2,
        "page_size": 15,
        "sort_by": "score",
        "sort_order": "desc",
    }


def test_search_resources_keeps_error_payload_recoverable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeService:
        @staticmethod
        async def search(**kwargs: Any) -> dict[str, Any]:
            return {"error": "search backend failed"}

    monkeypatch.setattr(search_api, "ResourceSearchService", FakeService)

    response = client.get("/api/search", params={"keyword": "movie"})

    assert response.status_code == 200
    assert response.json() == {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "has_more": False,
        "error": "search backend failed",
    }


def test_search_resources_maps_unexpected_exception_to_generic_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeService:
        @staticmethod
        async def search(**kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("network timeout")

    monkeypatch.setattr(search_api, "ResourceSearchService", FakeService)

    response = client.get("/api/search", params={"keyword": "movie"})

    assert response.status_code == 500
    assert response.json() == {"detail": "搜索失败"}


def test_search_resources_filtered_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeService:
        @staticmethod
        async def search(**kwargs: Any) -> dict[str, Any]:
            return {"items": [{"name": "ok"}], "page": kwargs["page"]}

    monkeypatch.setattr(search_api, "ResourceSearchService", FakeService)

    response = client.get("/api/search/filtered", params={"keyword": "show", "page": 3, "page_size": 30})

    assert response.status_code == 200
    assert response.json() == {"items": [{"name": "ok"}], "page": 3}


def test_search_resources_filtered_keeps_error_payload_recoverable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeService:
        @staticmethod
        async def search(**kwargs: Any) -> dict[str, Any]:
            return {"error": "filtered failed"}

    monkeypatch.setattr(search_api, "ResourceSearchService", FakeService)

    response = client.get("/api/search/filtered", params={"keyword": "show"})

    assert response.status_code == 200
    assert response.json() == {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "has_more": False,
        "error": "filtered failed",
    }


def test_search_resources_filtered_maps_exception_to_generic_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeService:
        @staticmethod
        async def search(**kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("boom")

    monkeypatch.setattr(search_api, "ResourceSearchService", FakeService)

    response = client.get("/api/search/filtered", params={"keyword": "show"})

    assert response.status_code == 500
    assert response.json() == {"detail": "过滤搜索失败"}


def test_get_search_status_reflects_sdk_availability(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sdk_config_module.sdk_config, "is_available", lambda: True)
    monkeypatch.setattr(sdk_config_module.sdk_config, "create_search_service", lambda: object())

    response = client.get("/api/search/status")

    assert response.status_code == 200
    assert response.json() == {"available": True, "search_service": True}


def test_get_search_status_handles_unavailable_sdk(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sdk_config_module.sdk_config, "is_available", lambda: False)
    monkeypatch.setattr(sdk_config_module.sdk_config, "create_search_service", lambda: None)

    response = client.get("/api/search/status")

    assert response.status_code == 200
    assert response.json() == {"available": False, "search_service": False}
