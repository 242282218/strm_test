from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import Request

from app.core.emby_proxy_request import is_dedicated_emby_proxy_request, is_emby_proxy_path


def build_request(path: str, host: str, scheme: str = "http") -> Request:
    headers = [(b"host", host.encode())]
    default_port = 80 if scheme == "http" else 443
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", default_port),
    }
    return Request(scope)


def test_is_emby_proxy_path_matches_native_and_api_aliases() -> None:
    assert is_emby_proxy_path("/emby/system/info/public") is True
    assert is_emby_proxy_path("/api/emby/items/144/PlaybackInfo") is True
    assert is_emby_proxy_path("/embywebsocket") is True
    assert is_emby_proxy_path("/api/protected") is False


def test_dedicated_proxy_request_when_default_port_and_emby_path_then_true() -> None:
    request = build_request("/emby/Users/authenticatebyname", "127.0.0.1:18097")

    assert is_dedicated_emby_proxy_request(request) is True


def test_dedicated_proxy_request_when_default_port_but_non_emby_path_then_false() -> None:
    request = build_request("/api/protected", "127.0.0.1:18097")

    assert is_dedicated_emby_proxy_request(request) is False


def test_dedicated_proxy_request_when_configured_proxy_base_url_matches_then_true() -> None:
    config = type("Cfg", (), {"emby": type("EmbyCfg", (), {"proxy_base_url": "http://proxy.example:19097"})()})()

    with patch("app.core.emby_proxy_request.get_config_service") as mock_get_config_service:
        mock_get_config_service.return_value.get_config.return_value = config
        request = build_request("/api/emby/items/144/PlaybackInfo", "proxy.example:19097")
        result = is_dedicated_emby_proxy_request(request)

    assert result is True


def test_dedicated_proxy_request_when_config_lookup_fails_then_false() -> None:
    with patch("app.core.emby_proxy_request.get_config_service", side_effect=RuntimeError("boom")):
        request = build_request("/emby/system/info/public", "proxy.example:19097")
        result = is_dedicated_emby_proxy_request(request)

    assert result is False


@pytest.mark.parametrize("host", ["proxy.example:notaport", "proxy.example:99999"])
def test_dedicated_proxy_request_when_host_port_is_invalid_then_false(host: str) -> None:
    request = build_request("/emby/system/info/public", host)

    assert is_dedicated_emby_proxy_request(request) is False
