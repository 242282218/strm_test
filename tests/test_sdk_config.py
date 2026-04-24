from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import patch

import app.core.sdk_config as sdk_config_module
from app.config.settings import AppConfig
from app.core.sdk_config import SDKConfig, get_api_keys
from app.services import config_service as config_service_module
from app.services.config_service import ConfigService


def _reset_config_service_singletons() -> None:
    ConfigService._instance = None
    config_service_module._config_service_instance = None


class _FakeConfigService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def get_config(self) -> AppConfig:
        return self._config


def test_get_api_keys_prefers_unified_ai_provider_key() -> None:
    config = AppConfig.model_validate(
        {
            "ai": {
                "providers": [
                    {
                        "name": "openai",
                        "api_key": "unified-openai-key",
                        "base_url": "https://api.openai.com/v1",
                        "model": "gpt-4o-mini",
                        "timeout": 30,
                    }
                ]
            },
            "zhipu": {"api_key": "legacy-zhipu-key"},
            "api_keys": {"ai_api_key": "legacy-generic-key", "tmdb_api_key": "tmdb-key"},
        }
    )

    with patch("app.core.sdk_config.get_config_service", return_value=_FakeConfigService(config)):
        api_keys = get_api_keys()

    assert api_keys["ai_api_key"] == "unified-openai-key"
    assert api_keys["tmdb_api_key"] == "tmdb-key"


def test_config_service_does_not_write_default_config_when_file_is_missing(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    _reset_config_service_singletons()

    try:
        service = ConfigService(str(config_path))

        assert service.get_config() is not None
        assert not config_path.exists()
    finally:
        _reset_config_service_singletons()


def test_config_service_reloads_when_missing_file_is_created(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    _reset_config_service_singletons()

    try:
        service = ConfigService(str(config_path))
        callback_calls: list[str] = []
        service.register_change_callback(lambda: callback_calls.append(service.get_config().quark.cookie))

        config_path.write_text("quark:\n  cookie: created-cookie\n", encoding="utf-8")

        service._check_for_changes()

        assert service.get_config().quark.cookie == "created-cookie"
        assert callback_calls == ["created-cookie"]
    finally:
        _reset_config_service_singletons()


def test_config_service_reloads_from_env_defaults_when_file_is_removed(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("quark:\n  cookie: file-cookie\n", encoding="utf-8")
    monkeypatch.setenv("SMART_MEDIA_QUARK_COOKIE", "env-cookie")
    _reset_config_service_singletons()

    try:
        service = ConfigService(str(config_path))
        callback_calls: list[str] = []
        service.register_change_callback(lambda: callback_calls.append(service.get_config().quark.cookie))

        config_path.unlink()
        service._check_for_changes()

        assert service.get_config().quark.cookie == "env-cookie"
        assert callback_calls == ["env-cookie"]
    finally:
        _reset_config_service_singletons()


def test_get_config_service_stops_previous_watcher_when_path_changes(tmp_path) -> None:
    first_path = tmp_path / "config-a.yaml"
    second_path = tmp_path / "config-b.yaml"
    first_path.write_text("quark:\n  cookie: first-cookie\n", encoding="utf-8")
    second_path.write_text("quark:\n  cookie: second-cookie\n", encoding="utf-8")
    _reset_config_service_singletons()

    try:
        first_service = config_service_module.get_config_service(str(first_path))
        first_service.start_watcher(interval_seconds=60)

        second_service = config_service_module.get_config_service(str(second_path))

        assert second_service is not first_service
        assert second_service.config_path == str(second_path)
        assert first_service._watcher_thread is None
        assert first_service._watcher_stop_event.is_set() is True
    finally:
        _reset_config_service_singletons()


def test_get_config_service_logs_resolved_paths_when_path_changes(tmp_path) -> None:
    first_path = tmp_path / "config-a.yaml"
    second_path = tmp_path / "config-b.yaml"
    first_path.write_text("quark:\n  cookie: first-cookie\n", encoding="utf-8")
    second_path.write_text("quark:\n  cookie: second-cookie\n", encoding="utf-8")
    _reset_config_service_singletons()

    try:
        config_service_module.get_config_service(str(first_path))

        with patch.object(config_service_module.logger, "warning") as mock_warning:
            config_service_module.get_config_service(str(second_path))

        mock_warning.assert_called_once_with(
            f"ConfigService path changed from {first_path} to {second_path}, reloading instance"
        )
    finally:
        _reset_config_service_singletons()


def test_config_service_callback_can_stop_watcher_from_current_thread() -> None:
    service = ConfigService.__new__(ConfigService)
    service._watcher_thread = threading.current_thread()
    service._watcher_stop_event = threading.Event()
    service._change_callbacks = [service.stop_watcher]

    with patch.object(config_service_module.logger, "error") as mock_error:
        service._notify_config_changed()

    assert service._watcher_thread is None
    assert service._watcher_stop_event.is_set() is True
    mock_error.assert_not_called()


def test_sdk_config_prefers_env_values_when_config_keys_absent(monkeypatch) -> None:
    monkeypatch.setattr(sdk_config_module, "get_api_keys", lambda: {})
    monkeypatch.setenv("SMART_MEDIA_TMDB_API_KEY", "env-tmdb")
    monkeypatch.setenv("SMART_MEDIA_AI_API_KEY", "env-ai")
    monkeypatch.setenv("SMART_MEDIA_QUARK_COOKIE", "cookie-value")

    config = SDKConfig()

    assert config.tmdb_api_key == "env-tmdb"
    assert config.ai_api_key == "env-ai"
    assert config.quark_cookie == "cookie-value"


def test_sdk_config_keeps_legacy_env_aliases_as_fallback(monkeypatch) -> None:
    monkeypatch.setattr(sdk_config_module, "get_api_keys", lambda: {})
    monkeypatch.setenv("TMDB_API_KEY", "legacy-tmdb")
    monkeypatch.setenv("AI_API_KEY", "legacy-ai")
    monkeypatch.setenv("QUARK_COOKIE", "legacy-cookie")

    config = SDKConfig()

    assert config.tmdb_api_key == "legacy-tmdb"
    assert config.ai_api_key == "legacy-ai"
    assert config.quark_cookie == "legacy-cookie"


def test_sdk_config_prefers_canonical_env_over_legacy_aliases(monkeypatch) -> None:
    monkeypatch.setattr(sdk_config_module, "get_api_keys", lambda: {})
    monkeypatch.setenv("SMART_MEDIA_TMDB_API_KEY", "canonical-tmdb")
    monkeypatch.setenv("TMDB_API_KEY", "legacy-tmdb")
    monkeypatch.setenv("SMART_MEDIA_AI_API_KEY", "canonical-ai")
    monkeypatch.setenv("AI_API_KEY", "legacy-ai")
    monkeypatch.setenv("SMART_MEDIA_QUARK_COOKIE", "canonical-cookie")
    monkeypatch.setenv("QUARK_COOKIE", "legacy-cookie")

    config = SDKConfig()

    assert config.tmdb_api_key == "canonical-tmdb"
    assert config.ai_api_key == "canonical-ai"
    assert config.quark_cookie == "canonical-cookie"


def test_create_clients_return_none_when_sdk_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(sdk_config_module, "get_api_keys", lambda: {})
    monkeypatch.setattr(sdk_config_module, "SDK_AVAILABLE", False)

    config = SDKConfig()

    assert config.is_available() is False
    assert config.get_quark_config() is None
    assert config.create_quark_client() is None
    assert config.create_async_quark_client() is None


def test_create_clients_build_instances_when_sdk_available(monkeypatch) -> None:
    class FakeConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeSyncClient:
        def __init__(self, *, config, cookie_string):
            self.config = config
            self.cookie_string = cookie_string

    class FakeAsyncClient:
        def __init__(self, *, config, cookie_string):
            self.config = config
            self.cookie_string = cookie_string

    monkeypatch.setattr(sdk_config_module, "get_api_keys", lambda: {"tmdb_api_key": "k1", "ai_api_key": "k2"})
    monkeypatch.setattr(sdk_config_module, "SDK_AVAILABLE", True)
    monkeypatch.setattr(sdk_config_module, "SDKQuarkConfig", FakeConfig)
    monkeypatch.setattr(sdk_config_module, "QuarkClient", FakeSyncClient)
    monkeypatch.setattr(sdk_config_module, "AsyncQuarkClient", FakeAsyncClient)

    config = SDKConfig()
    sync_client = config.create_quark_client(cookie="sync-cookie")
    async_client = config.create_async_quark_client()

    assert sync_client.cookie_string == "sync-cookie"
    assert sync_client.config.values["api__timeout"] == 30.0
    assert async_client.cookie_string == config.quark_cookie
    assert async_client.config.values["request__max_retries"] == 3


def test_create_rename_engine_returns_none_for_missing_sdk_or_engine(monkeypatch) -> None:
    monkeypatch.setattr(sdk_config_module, "get_api_keys", lambda: {"tmdb_api_key": "k1", "ai_api_key": "k2"})

    monkeypatch.setattr(sdk_config_module, "SDK_AVAILABLE", False)
    config = SDKConfig()
    assert config.create_rename_engine() is None

    monkeypatch.setattr(sdk_config_module, "SDK_AVAILABLE", True)
    monkeypatch.setattr(sdk_config_module, "RenameEngine", None)
    config = SDKConfig()
    assert config.create_rename_engine() is None


def test_create_rename_engine_handles_success_and_failure(monkeypatch) -> None:
    class FakeRenameEngine:
        def __init__(self, *, tmdb_api_key, ai_api_key, dry_run):
            self.tmdb_api_key = tmdb_api_key
            self.ai_api_key = ai_api_key
            self.dry_run = dry_run

    def raise_engine_error(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(sdk_config_module, "get_api_keys", lambda: {"tmdb_api_key": "tmdb", "ai_api_key": "ai"})
    monkeypatch.setattr(sdk_config_module, "SDK_AVAILABLE", True)
    monkeypatch.setattr(sdk_config_module, "RenameEngine", FakeRenameEngine)

    config = SDKConfig()
    engine = config.create_rename_engine()

    assert engine is not None
    assert engine.tmdb_api_key == "tmdb"
    assert engine.ai_api_key == "ai"
    assert engine.dry_run is True

    monkeypatch.setattr(sdk_config_module, "RenameEngine", raise_engine_error)
    failed = config.create_rename_engine()
    assert failed is None


def test_get_api_keys_returns_empty_dict_on_exception(monkeypatch) -> None:
    monkeypatch.setattr(sdk_config_module, "get_config_service", lambda: SimpleNamespace(get_config=lambda: (_ for _ in ()).throw(RuntimeError("x"))))
    assert get_api_keys() == {}
