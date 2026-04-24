from __future__ import annotations

from app.config.metadata import build_public_model_json_schema, collect_sensitive_fields_status
from app.config.runtime import apply_env_overrides, replace_env_placeholders
from app.config.settings import AppConfig


def test_apply_env_overrides_updates_unified_provider_key(monkeypatch) -> None:
    monkeypatch.setenv("SMART_MEDIA_DEEPSEEK_API_KEY", "canonical-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")

    data = {
        "ai": {
            "providers": [
                {
                    "name": "deepseek",
                    "api_key": "",
                    "base_url": "https://api.deepseek.com/v1",
                    "model": "deepseek-chat",
                    "timeout": 20,
                }
            ]
        }
    }

    overridden = apply_env_overrides(data)

    assert overridden["ai"]["providers"][0]["api_key"] == "canonical-key"


def test_apply_env_overrides_falls_back_to_legacy_provider_section(monkeypatch) -> None:
    monkeypatch.setenv("SMART_MEDIA_KIMI_API_KEY", "kimi-key")

    overridden = apply_env_overrides({})

    assert overridden["kimi"]["api_key"] == "kimi-key"


def test_replace_env_placeholders_supports_default_values(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    monkeypatch.setenv("SMART_MEDIA_HOST", "configured-host")

    payload = {
        "emby": {
            "url": "${SMART_MEDIA_HOST}",
            "proxy_base_url": "${MISSING_VAR:-http://localhost:8096}",
        }
    }

    replaced = replace_env_placeholders(payload)

    assert replaced == {
        "emby": {
            "url": "configured-host",
            "proxy_base_url": "http://localhost:8096",
        }
    }


def test_build_public_model_json_schema_hides_legacy_ai_sections() -> None:
    schema = build_public_model_json_schema(AppConfig)

    assert "ai" in schema["properties"]
    assert "zhipu" not in schema["properties"]
    assert "deepseek" not in schema["properties"]
    assert "glm" not in schema["properties"]
    assert "kimi" not in schema["properties"]


def test_collect_sensitive_fields_status_uses_unified_provider_list() -> None:
    config = AppConfig.model_validate(
        {
            "security": {"api_key": "security-key", "jwt_secret_key": "jwt-key", "require_api_key": True},
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
            "quark": {"cookie": "quark-cookie"},
        }
    )

    status = collect_sensitive_fields_status(config)

    assert status["ai.providers"] is True
    assert status["security.api_key"] is True
    assert status["security.jwt_secret_key"] is True
    assert status["quark.cookie"] is True
