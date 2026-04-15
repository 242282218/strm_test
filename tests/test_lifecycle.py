from __future__ import annotations

import warnings
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.config.lifecycle as lifecycle


class DummyConfigService:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def start_watcher(self) -> None:
        self.start_calls += 1

    def stop_watcher(self) -> None:
        self.stop_calls += 1


class DummyContainer:
    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop_services(self) -> None:
        self.stop_calls += 1


def _patch_lifecycle_dependencies(monkeypatch: pytest.MonkeyPatch, *, fail_on_start: bool) -> DummyContainer:
    container = DummyContainer()

    monkeypatch.setattr(lifecycle, "mount_webdav", lambda app, config: None)
    monkeypatch.setattr(lifecycle, "initialize_database", lambda: None)
    monkeypatch.setattr(lifecycle, "initialize_auth_system", lambda: None)
    monkeypatch.setattr(lifecycle, "configure_emby_cron", lambda _container: None)
    monkeypatch.setattr(lifecycle, "initialize_monitoring", lambda: None)

    async def fake_get_http_pool() -> object:
        return object()

    async def fake_start_service_container() -> DummyContainer:
        if fail_on_start:
            raise RuntimeError("startup exploded")
        return container

    monkeypatch.setattr(lifecycle, "get_http_pool", fake_get_http_pool)
    monkeypatch.setattr(lifecycle, "start_service_container", fake_start_service_container)
    return container


def _build_app(config_service: DummyConfigService) -> FastAPI:
    config = SimpleNamespace(webdav=SimpleNamespace(enabled=False))
    app = FastAPI(lifespan=lifecycle.create_lifespan_context(config_service, config))

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_lifespan_releases_resources_and_avoids_deprecation_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    config_service = DummyConfigService()
    container = _patch_lifecycle_dependencies(monkeypatch, fail_on_start=False)
    app = _build_app(config_service)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", DeprecationWarning)
        with TestClient(app) as client:
            response = client.get("/ping")
            assert response.status_code == 200
            assert response.json() == {"ok": True}

    assert config_service.start_calls == 1
    assert config_service.stop_calls == 1
    assert container.stop_calls == 1
    assert not any("async generator function lifespans are deprecated" in str(item.message) for item in captured)


def test_lifespan_stops_watcher_when_startup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    config_service = DummyConfigService()
    _patch_lifecycle_dependencies(monkeypatch, fail_on_start=True)
    app = _build_app(config_service)

    with pytest.raises(RuntimeError, match="startup exploded"):
        with TestClient(app):
            pass

    assert config_service.start_calls == 1
    assert config_service.stop_calls == 1
