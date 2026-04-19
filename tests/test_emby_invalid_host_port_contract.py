from __future__ import annotations

from copy import deepcopy
import runpy
import sys
from unittest.mock import patch

from fastapi.responses import Response
from fastapi.testclient import TestClient


MODULE_NAME = "app.main"


def _run_main_module(run_name: str) -> dict[str, object]:
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


def test_root_when_host_header_uses_invalid_port_then_falls_back_to_default_home() -> None:
    module_globals = _run_main_module("app.main_root_invalid_host_port_contract_test")
    app = module_globals["app"]
    app_config = _build_root_test_config(module_globals)

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            return_value=Response(content="unexpected-forward", media_type="text/plain"),
        ) as mock_forward,
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get("/", headers={"host": "proxy.example:notaport"})

    assert response.status_code == 200
    assert response.json() == {"name": "夸克 STRM 系统", "version": "0.1.0", "status": "running"}
    mock_forward.assert_not_called()
