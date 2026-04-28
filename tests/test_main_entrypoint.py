from __future__ import annotations

import os
import runpy
import sys
from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient


MODULE_NAME = "app.main"


def _run_main_module(run_name: str = "__main__") -> dict[str, object]:
    existing = sys.modules.pop(MODULE_NAME, None)
    try:
        return runpy.run_module(MODULE_NAME, run_name=run_name)
    finally:
        if existing is not None:
            sys.modules[MODULE_NAME] = existing
        else:
            sys.modules.pop(MODULE_NAME, None)


def _build_root_test_config(module_globals: dict[str, object]):
    config_path = module_globals["get_config_path"]()
    config_service = module_globals["get_config_service"](config_path)
    app_config = deepcopy(config_service.get_config())
    app_config.emby.proxy_base_url = "http://proxy.example:18097"
    app_config.emby.url = "http://emby.example:8096"
    return app_config


def test_main_entrypoint_uses_default_port_8000_and_single_worker() -> None:
    with patch.dict(os.environ, {}, clear=False), patch("uvicorn.run") as mock_run:
        _run_main_module("__main__")

    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8000
    assert kwargs["workers"] == 1


def test_main_entrypoint_respects_web_concurrency() -> None:
    with patch.dict(os.environ, {"WEB_CONCURRENCY": "4"}, clear=False), patch("uvicorn.run") as mock_run:
        _run_main_module("__main__")

    _, kwargs = mock_run.call_args
    assert kwargs["workers"] == 4
    assert kwargs["port"] == 8000


def test_main_import_does_not_initialize_app_before_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CONFIG_PATH", "config.yaml")

    module_globals = _run_main_module("app.main_import_test")

    assert module_globals["config"] is None
    assert module_globals["config_service"] is None
    assert not (tmp_path / "config.yaml").exists()
    assert not (tmp_path / "data").exists()


def test_resolve_startup_health_defaults_ok() -> None:
    module_globals = _run_main_module("app.main_health_default_test")
    app = module_globals["app"]
    resolver = module_globals["_resolve_startup_health"]

    app.state.startup_warnings = []
    app.state.startup_components = {"database": {"status": "ok", "detail": None}}

    status, warnings, components = resolver()

    assert status == "ok"
    assert warnings == []
    assert components["database"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_endpoint_returns_degraded_state_when_startup_has_warnings() -> None:
    module_globals = _run_main_module("app.main_health_degraded_test")
    app = module_globals["app"]
    health = module_globals["health"]

    app.state.started_at = datetime.utcnow()
    app.state.startup_warnings = ["monitoring: monitor exploded"]
    app.state.startup_components = {"monitoring": {"status": "degraded", "detail": "monitor exploded"}}

    payload = await health()

    assert payload["status"] == "degraded"
    assert payload["startup_warnings"] == ["monitoring: monitor exploded"]
    assert payload["startup_components"]["monitoring"]["status"] == "degraded"


@pytest.mark.asyncio
async def test_ready_probe_returns_503_when_required_components_missing() -> None:
    module_globals = _run_main_module("app.main_ready_missing_components_test")
    app = module_globals["app"]
    ready_probe = module_globals["ready_probe"]

    app.state.ready = False
    app.state.startup_components = {}

    payload = await ready_probe()

    assert isinstance(payload, JSONResponse)
    assert payload.status_code == 503
    assert b"startup_incomplete" in payload.body


@pytest.mark.asyncio
async def test_ready_probe_returns_ready_when_required_components_ok() -> None:
    module_globals = _run_main_module("app.main_ready_ok_test")
    app = module_globals["app"]
    ready_probe = module_globals["ready_probe"]

    app.state.ready = True
    app.state.startup_components = {
        "production_security": {"status": "ok", "detail": None},
        "database_migrations": {"status": "ok", "detail": "schema_version=1"},
        "database": {"status": "ok", "detail": None},
        "auth_system": {"status": "ok", "detail": None},
        "service_container": {"status": "ok", "detail": None},
        "http_pool": {"status": "ok", "detail": None},
        "task_worker": {"status": "ok", "detail": "owner=test-worker"},
    }

    payload = await ready_probe()

    assert payload["status"] == "ready"
    assert payload["readiness_problems"] == []


@pytest.mark.asyncio
async def test_ready_probe_accepts_non_production_security_skip() -> None:
    module_globals = _run_main_module("app.main_ready_non_production_security_skipped_test")
    app = module_globals["app"]
    ready_probe = module_globals["ready_probe"]

    app.state.ready = True
    app.state.startup_components = {
        "production_security": {"status": "skipped", "detail": "not production"},
        "database_migrations": {"status": "ok", "detail": "schema_version=1"},
        "database": {"status": "ok", "detail": None},
        "auth_system": {"status": "ok", "detail": None},
        "service_container": {"status": "ok", "detail": None},
        "http_pool": {"status": "ok", "detail": None},
        "task_worker": {"status": "ok", "detail": "owner=test-worker"},
    }

    payload = await ready_probe()

    assert payload["status"] == "ready"
    assert payload["readiness_problems"] == []


@pytest.mark.asyncio
async def test_ready_probe_returns_503_when_production_security_failed() -> None:
    module_globals = _run_main_module("app.main_ready_production_security_failed_test")
    app = module_globals["app"]
    ready_probe = module_globals["ready_probe"]

    app.state.ready = True
    app.state.startup_components = {
        "production_security": {"status": "failed", "detail": "Production requires security.api_key"},
        "database_migrations": {"status": "ok", "detail": "schema_version=1"},
        "database": {"status": "ok", "detail": None},
        "auth_system": {"status": "ok", "detail": None},
        "service_container": {"status": "ok", "detail": None},
        "http_pool": {"status": "ok", "detail": None},
        "task_worker": {"status": "ok", "detail": "owner=test-worker"},
    }

    payload = await ready_probe()

    assert isinstance(payload, JSONResponse)
    assert payload.status_code == 503
    assert b"production_security: failed" in payload.body


@pytest.mark.asyncio
async def test_live_probe_returns_alive_status() -> None:
    module_globals = _run_main_module("app.main_live_probe_test")
    app = module_globals["app"]
    live_probe = module_globals["live_probe"]
    app.state.started_at = datetime.utcnow()

    payload = await live_probe()

    assert payload["status"] == "alive"
    assert payload["uptime_seconds"] is not None


def test_probe_routes_are_reachable_before_catch_all_routes() -> None:
    module_globals = _run_main_module("app.main_probe_route_contract_test")
    app = module_globals["app"]

    with TestClient(app) as client:
        health = client.get("/health")
        live = client.get("/health/live")
        ready = client.get("/ready")
        health_ready = client.get("/health/ready")

    assert health.status_code == 200
    assert live.status_code == 200
    assert ready.status_code in {200, 503}
    assert health_ready.status_code in {200, 503}
    assert ready.json()["status"] in {"ready", "not_ready"}
    assert health_ready.json()["status"] in {"ready", "not_ready"}


def test_root_when_dedicated_proxy_request_and_emby_override_invalid_then_returns_400_before_forwarding() -> None:
    module_globals = _run_main_module("app.main_root_invalid_emby_override_test")
    app = module_globals["app"]
    app_config = _build_root_test_config(module_globals)

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            return_value=Response(content="emby-home", media_type="text/html"),
        ) as mock_forward,
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get(
            "/",
            headers={
                "host": "proxy.example:18097",
                "X-Emby-Server-Url": "not-a-url",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Emby server URL"
    mock_forward.assert_not_called()


def test_root_when_dedicated_proxy_request_and_proxy_override_invalid_then_returns_400_before_forwarding() -> None:
    module_globals = _run_main_module("app.main_root_invalid_proxy_override_test")
    app = module_globals["app"]
    app_config = _build_root_test_config(module_globals)

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            return_value=Response(content="emby-home", media_type="text/html"),
        ) as mock_forward,
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get(
            "/",
            headers={
                "host": "proxy.example:18097",
                "X-Proxy-Server-Url": "not-a-url",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid proxy server URL"
    mock_forward.assert_not_called()


def test_root_when_dedicated_proxy_request_then_passes_resolved_override_urls_to_gateway_forwarder() -> None:
    module_globals = _run_main_module("app.main_root_forward_override_contract_test")
    app = module_globals["app"]
    app_config = _build_root_test_config(module_globals)

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            return_value=Response(content="emby-home", media_type="text/html"),
        ) as mock_forward,
        TestClient(app) as client,
    ):
        response = client.get(
            "/",
            headers={
                "host": "proxy.example:18097",
                "X-Emby-Server-Url": "https://alt.emby.example:8920/base",
                "X-Proxy-Server-Url": "https://public.proxy.example/base",
            },
        )

    assert response.status_code == 200
    assert "emby-home" in response.text
    assert mock_forward.call_args.kwargs["emby_base_url"] == "https://alt.emby.example:8920/base"
    assert mock_forward.call_args.kwargs["proxy_base_url"] == "https://public.proxy.example/base"


@pytest.mark.parametrize(
    ("status_code", "detail", "message", "error_code"),
    [
        (502, "Failed to proxy Emby request", "上游服务异常", "ERR_BAD_GATEWAY"),
        (504, "Emby upstream timeout", "上游服务超时", "ERR_GATEWAY_TIMEOUT"),
    ],
)
def test_main_app_when_dedicated_gateway_forwarder_raises_upstream_http_exception_then_preserves_operational_contract(
    status_code: int,
    detail: str,
    message: str,
    error_code: str,
) -> None:
    module_globals = _run_main_module(f"app.main_gateway_upstream_http_exception_{status_code}_test")
    app = module_globals["app"]
    app_config = _build_root_test_config(module_globals)

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            side_effect=HTTPException(status_code=status_code, detail=detail),
        ) as mock_forward,
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get("/System/Info/Public", headers={"host": "proxy.example:18097"})

    payload = response.json()
    assert response.status_code == status_code
    assert payload["code"] == status_code
    assert payload["message"] == message
    assert payload["detail"] == detail
    assert payload["error_code"] == error_code
    mock_forward.assert_called_once()


@pytest.mark.parametrize(
    ("status_code", "detail", "message", "error_code"),
    [
        (502, "Failed to proxy Emby request", "上游服务异常", "ERR_BAD_GATEWAY"),
        (504, "Emby upstream timeout", "上游服务超时", "ERR_GATEWAY_TIMEOUT"),
    ],
)
def test_root_when_dedicated_proxy_forwarder_raises_upstream_http_exception_then_preserves_operational_contract(
    status_code: int,
    detail: str,
    message: str,
    error_code: str,
) -> None:
    module_globals = _run_main_module(f"app.main_root_upstream_http_exception_{status_code}_test")
    app = module_globals["app"]
    app_config = _build_root_test_config(module_globals)

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            side_effect=HTTPException(status_code=status_code, detail=detail),
        ) as mock_forward,
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get("/", headers={"host": "proxy.example:18097"})

    payload = response.json()
    assert response.status_code == status_code
    assert payload["code"] == status_code
    assert payload["message"] == message
    assert payload["detail"] == detail
    assert payload["error_code"] == error_code
    mock_forward.assert_called_once()


def test_root_when_dedicated_proxy_forwarder_raises_generic_exception_then_maps_to_fixed_502_contract() -> None:
    module_globals = _run_main_module("app.main_root_generic_forward_exception_test")
    app = module_globals["app"]
    app_config = _build_root_test_config(module_globals)

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            side_effect=RuntimeError("dial exploded"),
        ) as mock_forward,
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get("/", headers={"host": "proxy.example:18097"})

    payload = response.json()
    assert response.status_code == 502
    assert payload["code"] == 502
    assert payload["message"] == "上游服务异常"
    assert payload["detail"] == "Failed to proxy Emby home"
    assert payload["error_code"] == "ERR_BAD_GATEWAY"
    mock_forward.assert_called_once()
