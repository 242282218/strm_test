"""
Configuration metadata helpers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


LEGACY_AI_SCHEMA_KEYS: set[str] = {"zhipu", "deepseek", "glm", "kimi"}
LEGACY_AI_SENSITIVE_KEYS: set[str] = {"zhipu.api_key", "deepseek.api_key", "glm.api_key", "kimi.api_key"}


def build_public_model_json_schema(
    config_model: type[BaseModel],
    hidden_properties: set[str] = LEGACY_AI_SCHEMA_KEYS,
) -> dict[str, Any]:
    schema = config_model.model_json_schema()
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for key in hidden_properties:
            properties.pop(key, None)
    return schema


def collect_sensitive_fields_status(config: Any) -> dict[str, bool]:
    api_keys = getattr(config, "api_keys", None)
    ai_config = getattr(config, "ai", None)
    ai_providers = getattr(ai_config, "providers", []) if ai_config else []

    return {
        "api_keys.ai_api_key": bool(api_keys and getattr(api_keys, "ai_api_key", None)),
        "api_keys.tmdb_api_key": bool(api_keys and getattr(api_keys, "tmdb_api_key", None)),
        "ai.providers": any(bool(getattr(provider, "api_key", None)) for provider in ai_providers),
        "quark.cookie": bool(getattr(getattr(config, "quark", None), "cookie", None)),
        "emby.api_key": bool(getattr(getattr(config, "emby", None), "api_key", None)),
        "telegram.bot_token": bool(getattr(getattr(config, "telegram", None), "bot_token", None)),
        "security.api_key": bool(getattr(getattr(config, "security", None), "api_key", None)),
        "security.jwt_secret_key": bool(getattr(getattr(config, "security", None), "jwt_secret_key", None)),
        "tmdb.api_key": bool(getattr(getattr(config, "tmdb", None), "api_key", None)),
        "webdav.password": bool(getattr(getattr(config, "webdav", None), "password", None)),
        "alist.token": bool(getattr(getattr(config, "alist", None), "token", None)),
        "wechat.send_key": bool(getattr(getattr(config, "wechat", None), "send_key", None)),
    }
