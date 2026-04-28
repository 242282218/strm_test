from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.system_config import router as system_config_router
from app.config.settings import AppConfig
from app.core.dependencies import require_api_key
from app.core.security import mask_secret, mask_sensitive_data


class FakeConfigService:
    def __init__(self, config_dict: dict[str, Any]) -> None:
        self._config = AppConfig.model_validate(config_dict)
        self.last_update_payload: dict[str, Any] | None = None

    def get_config(self) -> AppConfig:
        return self._config

    def get_safe_config(self) -> dict[str, Any]:
        return mask_sensitive_data(self._config.model_dump())

    def update_config(self, new_config: dict[str, Any]) -> AppConfig:
        self.last_update_payload = deepcopy(new_config)
        self._config = AppConfig.model_validate(new_config)
        return self._config


def create_client() -> TestClient:
    app = FastAPI()
    app.include_router(system_config_router)
    app.dependency_overrides[require_api_key] = lambda: None
    return TestClient(app)


def test_update_config_preserves_masked_sensitive_values() -> None:
    client = create_client()
    service = FakeConfigService(
        {
            "log_level": "INFO",
            "security": {"api_key": "very-secret-api-key", "require_api_key": True},
            "telegram": {"enabled": True, "bot_token": "telegram-bot-token", "chat_id": "10001"},
            "quark": {"cookie": "quark-cookie-value", "root_id": "0"},
        }
    )

    payload = service.get_safe_config()
    payload["log_level"] = "DEBUG"

    with patch("app.api.system_config.get_config_service", return_value=service):
        response = client.post("/api/system-config/", json=payload)

    assert response.status_code == 200
    assert service.last_update_payload is not None
    assert service.last_update_payload["log_level"] == "DEBUG"
    assert service.last_update_payload["security"]["api_key"] == "very-secret-api-key"
    assert service.last_update_payload["telegram"]["bot_token"] == "telegram-bot-token"
    assert service.last_update_payload["quark"]["cookie"] == "quark-cookie-value"


def test_update_config_merges_partial_payload_without_resetting_existing_fields() -> None:
    client = create_client()
    service = FakeConfigService(
        {
            "log_level": "INFO",
            "security": {"api_key": "keep-this-key", "require_api_key": True},
            "telegram": {"enabled": True, "bot_token": "keep-this-bot", "chat_id": "20002"},
            "emby": {"enabled": True, "url": "http://localhost:8096", "api_key": "keep-emby-key"},
        }
    )

    payload = {
        "log_level": "WARNING",
        "security": {"api_key": mask_secret("keep-this-key")},
    }

    with patch("app.api.system_config.get_config_service", return_value=service):
        response = client.post("/api/system-config/", json=payload)

    assert response.status_code == 200
    assert service.last_update_payload is not None
    assert service.last_update_payload["log_level"] == "WARNING"
    assert service.last_update_payload["security"]["api_key"] == "keep-this-key"
    assert service.last_update_payload["telegram"]["bot_token"] == "keep-this-bot"
    assert service.last_update_payload["emby"]["api_key"] == "keep-emby-key"


def test_update_config_allows_updating_sensitive_values() -> None:
    client = create_client()
    service = FakeConfigService(
        {
            "security": {"api_key": "old-api-key", "require_api_key": True},
            "telegram": {"enabled": True, "bot_token": "old-telegram-token", "chat_id": "30003"},
        }
    )

    payload = service.get_safe_config()
    payload["security"]["api_key"] = "new-api-key"
    payload["telegram"]["bot_token"] = "new-telegram-token"

    with patch("app.api.system_config.get_config_service", return_value=service):
        response = client.post("/api/system-config/", json=payload)

    assert response.status_code == 200
    assert service.last_update_payload is not None
    assert service.last_update_payload["security"]["api_key"] == "new-api-key"
    assert service.last_update_payload["telegram"]["bot_token"] == "new-telegram-token"


def test_update_config_keeps_sensitive_values_when_empty_strings_are_submitted() -> None:
    client = create_client()
    service = FakeConfigService(
        {
            "security": {"api_key": "keep-api-key", "require_api_key": True},
            "telegram": {"enabled": True, "bot_token": "keep-telegram-token", "chat_id": "40004"},
            "webdav": {"enabled": True, "username": "dav-user", "password": "keep-dav-password"},
        }
    )

    payload = service.get_safe_config()
    payload["security"]["api_key"] = ""
    payload["telegram"]["bot_token"] = ""
    payload["webdav"]["password"] = ""

    with patch("app.api.system_config.get_config_service", return_value=service):
        response = client.post("/api/system-config/", json=payload)

    assert response.status_code == 200
    assert service.last_update_payload is not None
    assert service.last_update_payload["security"]["api_key"] == "keep-api-key"
    assert service.last_update_payload["telegram"]["bot_token"] == "keep-telegram-token"
    assert service.last_update_payload["webdav"]["password"] == "keep-dav-password"


def test_get_config_metadata_returns_schema_and_sensitive_field_status() -> None:
    client = create_client()
    service = FakeConfigService(
        {
            "security": {"api_key": "meta-api-key", "require_api_key": True},
        }
    )

    with patch("app.api.system_config.get_config_service", return_value=service):
        response = client.get("/api/system-config/metadata")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"]["type"] == "object"
    assert "telegram" in payload["schema"]["properties"]
    assert "ai" in payload["schema"]["properties"]
    assert "zhipu" not in payload["schema"]["properties"]
    assert "deepseek" not in payload["schema"]["properties"]
    assert "glm" not in payload["schema"]["properties"]
    assert "kimi" not in payload["schema"]["properties"]
    assert payload["sensitive_fields"] == sorted(payload["sensitive_fields"])
    assert "security.api_key" in payload["sensitive_fields"]
    assert "security.jwt_secret_key" in payload["sensitive_fields"]
    assert "zhipu.api_key" not in payload["sensitive_fields_status"]
    assert "deepseek.api_key" not in payload["sensitive_fields_status"]
    assert "glm.api_key" not in payload["sensitive_fields_status"]
    assert "kimi.api_key" not in payload["sensitive_fields_status"]
    assert payload["sensitive_fields_status"]["security.api_key"] is True
    assert payload["sensitive_fields_status"]["security.jwt_secret_key"] is False
    assert payload["sensitive_fields_status"]["webdav.password"] is False


def test_get_ai_providers_returns_only_unified_provider_list() -> None:
    client = create_client()
    service = FakeConfigService(
        {
            "ai": {
                "providers": [
                    {
                        "name": "openai",
                        "api_key": "openai-key",
                        "base_url": "https://api.openai.com/v1",
                        "model": "gpt-4o-mini",
                        "timeout": 30,
                        "enabled": True,
                        "priority": 100,
                    }
                ]
            }
        }
    )

    with patch("app.api.system_config.get_config_service", return_value=service):
        response = client.get("/api/system-config/ai-providers")

    assert response.status_code == 200
    assert response.json() == {
        "providers": [
            {
                "name": "openai",
                "api_key_masked": mask_secret("openai-key"),
                "configured": True,
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "timeout": 30,
                "enabled": True,
                "priority": 100,
            }
        ]
    }


def test_legacy_ai_models_endpoint_is_removed() -> None:
    client = create_client()

    response = client.get("/api/system-config/ai-models")

    assert response.status_code == 404


def test_app_config_public_schema_hides_legacy_ai_sections() -> None:
    schema = AppConfig.public_model_json_schema()
    properties = schema["properties"]

    assert "ai" in properties
    assert "zhipu" not in properties
    assert "deepseek" not in properties
    assert "glm" not in properties
    assert "kimi" not in properties


def test_app_config_sensitive_fields_status_uses_unified_ai_key() -> None:
    config = AppConfig.model_validate(
        {
            "security": {"api_key": "meta-api-key", "jwt_secret_key": "jwt-secret", "require_api_key": True},
            "ai": {
                "providers": [
                    {
                        "name": "openai",
                        "api_key": "openai-key",
                        "base_url": "https://api.openai.com/v1",
                        "model": "gpt-4o-mini",
                        "timeout": 30,
                    }
                ]
            },
        }
    )

    sensitive_status = config.get_sensitive_fields_status()

    assert sensitive_status["ai.providers"] is True
    assert "zhipu.api_key" not in sensitive_status
    assert "deepseek.api_key" not in sensitive_status
    assert "glm.api_key" not in sensitive_status
    assert "kimi.api_key" not in sensitive_status
    assert sensitive_status["security.jwt_secret_key"] is True


def test_app_config_absorbs_legacy_ai_sections_into_unified_providers() -> None:
    config = AppConfig.model_validate(
        {
            "deepseek": {
                "api_key": "deepseek-key",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "timeout": 20,
            },
            "glm": {
                "api_key": "glm-key",
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model": "glm-4.7-flash",
                "timeout": 8,
            },
            "kimi": {
                "api_key": "kimi-key",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "model": "moonshotai/kimi-k2.5",
                "timeout": 15,
            },
            "zhipu": {"api_key": "zhipu-key"},
        }
    )

    provider_names = [provider.name for provider in config.ai.providers]
    dumped = config.model_dump()

    assert provider_names == ["deepseek", "glm", "kimi", "zhipu"]
    assert not hasattr(config, "deepseek")
    assert not hasattr(config, "glm")
    assert not hasattr(config, "kimi")
    assert not hasattr(config, "zhipu")
    assert "deepseek" not in dumped
    assert "glm" not in dumped
    assert "kimi" not in dumped
    assert "zhipu" not in dumped


def test_get_config_metadata_does_not_leak_internal_error_details() -> None:
    client = create_client()

    with patch(
        "app.api.system_config.get_config_service", side_effect=RuntimeError("metadata exploded: secret config path")
    ):
        response = client.get("/api/system-config/metadata")

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to read config metadata"}


def test_get_config_does_not_leak_internal_error_details() -> None:
    client = create_client()

    with patch(
        "app.api.system_config.get_config_service", side_effect=RuntimeError("config exploded: secret config path")
    ):
        response = client.get("/api/system-config/")

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to read config"}


def test_update_config_does_not_leak_internal_error_details() -> None:
    client = create_client()

    with patch(
        "app.api.system_config.get_config_service", side_effect=RuntimeError("save exploded: secret config path")
    ):
        response = client.post("/api/system-config/", json={"log_level": "INFO"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to save config"}


def test_get_ai_providers_does_not_leak_internal_error_details() -> None:
    client = create_client()

    with patch(
        "app.api.system_config.get_config_service", side_effect=RuntimeError("providers exploded: secret config path")
    ):
        response = client.get("/api/system-config/ai-providers")

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to read AI providers"}


def test_update_ai_providers_does_not_leak_internal_error_details() -> None:
    client = create_client()

    payload = {
        "providers": [
            {
                "name": "openai",
                "api_key": "openai-key",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "timeout": 30,
                "enabled": True,
                "priority": 100,
            }
        ]
    }

    with patch(
        "app.api.system_config.get_config_service",
        side_effect=RuntimeError("update providers exploded: secret config path"),
    ):
        response = client.post("/api/system-config/ai-providers", json=payload)

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to update AI providers"}


def test_app_config_schema_text_does_not_contain_known_mojibake() -> None:
    schema = AppConfig.model_json_schema()
    schema_text = str(schema)

    assert "鍏ㄥ眬Emby 配置" not in schema_text
    assert "全局 Emby 配置" in schema_text
