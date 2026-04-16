from __future__ import annotations

import sys
import types
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
    monkeypatch.setattr(lifecycle, "configure_emby_cron", lambda _container: (True, None))
    monkeypatch.setattr(lifecycle, "initialize_monitoring", lambda: (True, None))

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


def test_initialize_database_uses_resolved_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_bind = {"value": None}
    monkeypatch.setattr(lifecycle, "get_engine", lambda: "fake-engine")
    monkeypatch.setattr(
        lifecycle.Base.metadata,
        "create_all",
        lambda **kwargs: captured_bind.update(value=kwargs.get("bind")),
    )

    lifecycle.initialize_database()

    assert captured_bind["value"] == "fake-engine"


def test_initialize_auth_system_calls_initializer(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}
    fake_module = types.ModuleType("app.services.auth_service")
    fake_module.init_auth_system = lambda: called.update(count=called["count"] + 1)
    monkeypatch.setitem(sys.modules, "app.services.auth_service", fake_module)

    lifecycle.initialize_auth_system()

    assert called["count"] == 1


@pytest.mark.asyncio
async def test_start_service_container_starts_services(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeContainer:
        def __init__(self) -> None:
            self.start_calls = 0

        async def start_services(self) -> None:
            self.start_calls += 1

    container = FakeContainer()
    monkeypatch.setattr(lifecycle, "initialize_service_container", lambda: container)

    resolved_container = await lifecycle.start_service_container()

    assert resolved_container is container
    assert container.start_calls == 1


def test_configure_emby_cron_runs_when_service_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeEmbyService:
        def __init__(self) -> None:
            self.configure_calls = 0

        def configure_cron(self) -> None:
            self.configure_calls += 1

    service = FakeEmbyService()

    class FakeContainer:
        def get(self, cls):
            assert cls is FakeEmbyService
            return service

    fake_module = types.ModuleType("app.services.emby_service")
    fake_module.EmbyService = FakeEmbyService
    monkeypatch.setitem(sys.modules, "app.services.emby_service", fake_module)

    ok, detail = lifecycle.configure_emby_cron(FakeContainer())

    assert service.configure_calls == 1
    assert ok is True
    assert detail is None


def test_configure_emby_cron_swallows_service_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeEmbyService:
        pass

    class FakeContainer:
        def get(self, cls):
            raise RuntimeError("cron setup failed")

    fake_module = types.ModuleType("app.services.emby_service")
    fake_module.EmbyService = FakeEmbyService
    monkeypatch.setitem(sys.modules, "app.services.emby_service", fake_module)

    ok, detail = lifecycle.configure_emby_cron(FakeContainer())
    assert ok is False
    assert "cron setup failed" in detail


def test_initialize_monitoring_handles_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    success_calls = {"count": 0}
    success_module = types.ModuleType("app.core.metrics_collector")
    success_module.setup_default_monitoring = lambda: success_calls.update(count=success_calls["count"] + 1)
    monkeypatch.setitem(sys.modules, "app.core.metrics_collector", success_module)

    ok, detail = lifecycle.initialize_monitoring()
    assert ok is True
    assert detail is None
    assert success_calls["count"] == 1

    failed_module = types.ModuleType("app.core.metrics_collector")
    failed_module.setup_default_monitoring = lambda: (_ for _ in ()).throw(RuntimeError("monitor exploded"))
    monkeypatch.setitem(sys.modules, "app.core.metrics_collector", failed_module)

    ok, detail = lifecycle.initialize_monitoring()
    assert ok is False
    assert "monitor exploded" in detail


def test_lifespan_records_degraded_optional_components(monkeypatch: pytest.MonkeyPatch) -> None:
    config_service = DummyConfigService()
    container = DummyContainer()

    monkeypatch.setattr(lifecycle, "mount_webdav", lambda app, config: None)
    monkeypatch.setattr(lifecycle, "initialize_database", lambda: None)
    monkeypatch.setattr(lifecycle, "initialize_auth_system", lambda: None)
    monkeypatch.setattr(lifecycle, "configure_emby_cron", lambda _container: (False, "cron setup failed"))
    monkeypatch.setattr(lifecycle, "initialize_monitoring", lambda: (False, "monitor exploded"))

    async def fake_get_http_pool() -> object:
        return object()

    async def fake_start_service_container() -> DummyContainer:
        return container

    monkeypatch.setattr(lifecycle, "get_http_pool", fake_get_http_pool)
    monkeypatch.setattr(lifecycle, "start_service_container", fake_start_service_container)

    app = _build_app(config_service)
    with TestClient(app):
        pass

    assert app.state.startup_components["emby_cron"]["status"] == "degraded"
    assert app.state.startup_components["monitoring"]["status"] == "degraded"
    assert "emby_cron: cron setup failed" in app.state.startup_warnings
    assert "monitoring: monitor exploded" in app.state.startup_warnings


def test_lifespan_resets_startup_tracking_each_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    config_service = DummyConfigService()
    container = DummyContainer()
    fail_once = {"value": True}

    monkeypatch.setattr(lifecycle, "mount_webdav", lambda app, config: None)
    monkeypatch.setattr(lifecycle, "initialize_database", lambda: None)
    monkeypatch.setattr(lifecycle, "initialize_auth_system", lambda: None)
    monkeypatch.setattr(
        lifecycle,
        "configure_emby_cron",
        lambda _container: (False, "cron setup failed") if fail_once["value"] else (True, None),
    )
    monkeypatch.setattr(lifecycle, "initialize_monitoring", lambda: (True, None))

    async def fake_get_http_pool() -> object:
        return object()

    async def fake_start_service_container() -> DummyContainer:
        return container

    monkeypatch.setattr(lifecycle, "get_http_pool", fake_get_http_pool)
    monkeypatch.setattr(lifecycle, "start_service_container", fake_start_service_container)

    app = _build_app(config_service)
    with TestClient(app):
        pass

    assert app.state.startup_components["emby_cron"]["status"] == "degraded"
    assert app.state.startup_warnings == ["emby_cron: cron setup failed"]

    fail_once["value"] = False
    with TestClient(app):
        pass

    assert app.state.startup_components["emby_cron"]["status"] == "ok"
    assert app.state.startup_warnings == []


def test_mount_webdav_mounts_once_and_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    mounts: list[tuple[str, object]] = []
    monkeypatch.setattr(app, "mount", lambda path, mounted_app: mounts.append((path, mounted_app)))

    class FakeWsgiToAsgi:
        def __init__(self, wsgi_app: object) -> None:
            self.wsgi_app = wsgi_app

    asgi_module = types.ModuleType("asgiref.wsgi")
    asgi_module.WsgiToAsgi = FakeWsgiToAsgi
    monkeypatch.setitem(sys.modules, "asgiref.wsgi", asgi_module)

    webdav_module = types.ModuleType("app.services.webdav.service")
    webdav_module.get_webdav_app = lambda: object()
    monkeypatch.setitem(sys.modules, "app.services.webdav.service", webdav_module)

    lifecycle.mount_webdav(app, None)
    lifecycle.mount_webdav(app, SimpleNamespace(webdav=SimpleNamespace(enabled=False, mount_path="/dav")))
    lifecycle.mount_webdav(app, SimpleNamespace(webdav=SimpleNamespace(enabled=True, mount_path="/dav")))
    lifecycle.mount_webdav(app, SimpleNamespace(webdav=SimpleNamespace(enabled=True, mount_path="/dav")))

    assert len(mounts) == 1
    assert mounts[0][0] == "/dav"
    assert app.state.webdav_mounted is True


def test_mount_webdav_skips_when_webdav_app_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    mounted = {"count": 0}
    monkeypatch.setattr(app, "mount", lambda *_args, **_kwargs: mounted.update(count=mounted["count"] + 1))

    class FakeWsgiToAsgi:
        def __init__(self, wsgi_app: object) -> None:
            self.wsgi_app = wsgi_app

    asgi_module = types.ModuleType("asgiref.wsgi")
    asgi_module.WsgiToAsgi = FakeWsgiToAsgi
    monkeypatch.setitem(sys.modules, "asgiref.wsgi", asgi_module)

    webdav_module = types.ModuleType("app.services.webdav.service")
    webdav_module.get_webdav_app = lambda: None
    monkeypatch.setitem(sys.modules, "app.services.webdav.service", webdav_module)

    lifecycle.mount_webdav(app, SimpleNamespace(webdav=SimpleNamespace(enabled=True, mount_path="/dav")))

    assert mounted["count"] == 0
    assert not getattr(app.state, "webdav_mounted", False)


def test_create_lifespan_context_uses_initializer_when_inputs_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    config_service = DummyConfigService()
    config = SimpleNamespace(webdav=SimpleNamespace(enabled=False))
    _patch_lifecycle_dependencies(monkeypatch, fail_on_start=False)
    app = FastAPI(lifespan=lifecycle.create_lifespan_context(None, None, initializer=lambda: (config_service, config)))

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200

    assert app.state.config_service is config_service
    assert app.state.config is config
