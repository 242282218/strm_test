from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.integrations import emby as emby_mod
from app.services.media import organize as organize_mod
from app.services.media import rename as rename_mod
from app.services.media import smart_rename as smart_rename_mod
from app.services.media import strm_generator as strm_generator_mod


def _build_runtime_config(**overrides):
    base = {
        "tmdb": SimpleNamespace(api_key=""),
        "api_keys": SimpleNamespace(tmdb_api_key=""),
        "quark": SimpleNamespace(cookie="", root_id="0", only_video=True),
        "webdav": SimpleNamespace(
            enabled=False,
            fallback_enabled=True,
            mount_path="/dav",
            username="",
            password="",
            url="http://localhost:5244/dav",
        ),
        "emby": SimpleNamespace(
            enabled=False,
            url="",
            api_key="",
            timeout=30,
            notify_on_complete=True,
            refresh=SimpleNamespace(on_strm_generate=True, on_rename=True, cron=None, library_ids=[]),
        ),
        "endpoints": [SimpleNamespace(emby_url="", emby_api_key="")],
        "timeout": 45,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("module", [rename_mod, smart_rename_mod])
def test_media_services_prefer_canonical_tmdb_key(monkeypatch: pytest.MonkeyPatch, module) -> None:
    config = _build_runtime_config(
        tmdb=SimpleNamespace(api_key="canonical-key"),
        api_keys=SimpleNamespace(tmdb_api_key="legacy-key"),
    )
    monkeypatch.setattr(module, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))

    assert module._resolve_tmdb_api_key() == "canonical-key"


@pytest.mark.parametrize("module", [rename_mod, smart_rename_mod])
def test_media_services_fall_back_to_legacy_tmdb_key(monkeypatch: pytest.MonkeyPatch, module) -> None:
    config = _build_runtime_config(
        tmdb=SimpleNamespace(api_key=""),
        api_keys=SimpleNamespace(tmdb_api_key="legacy-key"),
    )
    monkeypatch.setattr(module, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))

    assert module._resolve_tmdb_api_key() == "legacy-key"


def test_strm_generator_runtime_config_facade_reads_runtime_app_config(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _build_runtime_config(
        quark=SimpleNamespace(cookie="cookie-1", root_id="root-9", only_video=False),
        webdav=SimpleNamespace(
            enabled=True,
            fallback_enabled=True,
            mount_path="/dav",
            username="alice",
            password="secret",
            url="http://localhost:5244/dav",
        ),
    )
    monkeypatch.setattr(strm_generator_mod, "config_service", SimpleNamespace(get_config=lambda: config))

    runtime_config = strm_generator_mod.get_config()

    assert runtime_config.get_quark_cookie() == "cookie-1"
    assert runtime_config.get_quark_root_id() == "root-9"
    assert runtime_config.get_quark_only_video() is False
    assert runtime_config.get_webdav_config()["username"] == "alice"


def test_media_organize_runtime_config_facade_reads_runtime_values_and_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_runtime_config(
        quark=SimpleNamespace(cookie="cookie-2", root_id="0", only_video=True),
        webdav=SimpleNamespace(
            enabled=True,
            fallback_enabled=True,
            mount_path="/dav",
            username="bob",
            password="pw",
            url="http://localhost:5244/dav",
        ),
    )
    monkeypatch.setattr(organize_mod, "config_service", SimpleNamespace(get_config=lambda: config))

    runtime_config = organize_mod._RuntimeOrganizeConfigFacade()

    assert runtime_config.get("quark.cookie") == "cookie-2"
    assert runtime_config.get("webdav.username") == "bob"
    assert runtime_config.get("webdav.password") == "pw"
    assert runtime_config.get("app.host", "localhost") == "localhost"
    assert runtime_config.get("app.port", 8000) == 8000


def test_emby_runtime_settings_fall_back_to_legacy_endpoint_values() -> None:
    config = _build_runtime_config(
        emby=SimpleNamespace(
            enabled=False,
            url="",
            api_key="",
            timeout=12,
            notify_on_complete=False,
            refresh=SimpleNamespace(on_strm_generate=False, on_rename=True, cron="0 0 * * *", library_ids=[1, "2"]),
        ),
        endpoints=[SimpleNamespace(emby_url="http://legacy.emby", emby_api_key="legacy-token")],
        timeout=99,
    )

    settings = emby_mod._resolve_effective_settings(config)

    assert settings == {
        "enabled": True,
        "url": "http://legacy.emby",
        "api_key": "legacy-token",
        "timeout": 12,
        "notify_on_complete": False,
        "refresh": {
            "on_strm_generate": False,
            "on_rename": True,
            "cron": "0 0 * * *",
            "library_ids": ["1", "2"],
        },
    }
