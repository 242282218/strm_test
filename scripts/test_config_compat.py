from app.config.settings import AppConfig, EndpointConfig
from app.services import config_service as config_module
from app.services.emby_service import EmbyService


class _DummyConfigService:
    def __init__(self, cfg):
        self._cfg = cfg

    def get_config(self):
        return self._cfg

    def reload(self):
        return None


class _FakeConfigReader:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_get_nested_value_supports_list_index_for_dict():
    data = {"endpoints": [{"emby_url": "http://legacy:8096"}]}
    assert config_module._get_nested_value(data, "endpoints.0.emby_url") == "http://legacy:8096"


def test_config_manager_get_supports_list_index_for_app_config(monkeypatch):
    cfg = AppConfig(
        endpoints=[
            EndpointConfig(
                base_url="http://alist:5244",
                emby_url="http://emby:8096",
                emby_api_key="secret",
            )
        ]
    )
    monkeypatch.setattr(
        config_module,
        "get_config_service",
        lambda config_path=None: _DummyConfigService(cfg),
    )
    manager = config_module.ConfigManager("config.yaml")
    assert manager.get("endpoints.0.emby_url") == "http://emby:8096"


def _base_emby_values():
    return {
        "emby.enabled": False,
        "emby.url": "",
        "emby.api_key": "",
        "emby.timeout": 30,
        "timeout": 30,
        "emby.notify_on_complete": True,
        "emby.refresh.on_strm_generate": True,
        "emby.refresh.on_rename": True,
        "emby.refresh.cron": None,
        "emby.refresh.library_ids": [],
        "endpoints.0.emby_url": "",
        "endpoints.0.emby_api_key": "",
    }


def test_emby_effective_settings_fallback_to_legacy_endpoints():
    values = _base_emby_values()
    values.update(
        {
            "endpoints.0.emby_url": "http://legacy:8096",
            "endpoints.0.emby_api_key": "legacy-key",
        }
    )
    service = EmbyService()
    service.config = _FakeConfigReader(values)

    settings = service._get_effective_settings()
    assert settings["enabled"] is True
    assert settings["url"] == "http://legacy:8096"
    assert settings["api_key"] == "legacy-key"


def test_emby_effective_settings_prioritize_global_when_present():
    values = _base_emby_values()
    values.update(
        {
            "emby.enabled": True,
            "emby.url": "http://global:8096",
            "emby.api_key": "global-key",
            "endpoints.0.emby_url": "http://legacy:8096",
            "endpoints.0.emby_api_key": "legacy-key",
        }
    )
    service = EmbyService()
    service.config = _FakeConfigReader(values)

    settings = service._get_effective_settings()
    assert settings["enabled"] is True
    assert settings["url"] == "http://global:8096"
    assert settings["api_key"] == "global-key"
