from __future__ import annotations

import os
import runpy
import sys
from datetime import datetime
from unittest.mock import patch

import pytest


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


def test_main_entrypoint_uses_default_port_8000_and_single_worker() -> None:
    with patch.dict(os.environ, {}, clear=False):
        with patch("uvicorn.run") as mock_run:
            _run_main_module("__main__")

    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8000
    assert kwargs["workers"] == 1


def test_main_entrypoint_respects_web_concurrency() -> None:
    with patch.dict(os.environ, {"WEB_CONCURRENCY": "4"}, clear=False):
        with patch("uvicorn.run") as mock_run:
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
