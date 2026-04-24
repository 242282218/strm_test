"""
Configuration loading and serialization helpers.
"""

from __future__ import annotations

import os
import re
from copy import deepcopy
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from app.core.env_aliases import AI_PROVIDER_API_KEY_ENV_PRIORITY, get_provider_api_key_env_override


ConfigModelT = TypeVar("ConfigModelT", bound=BaseModel)

ENV_OVERRIDE_MAP: dict[str, list[str]] = {
    "SMART_MEDIA_AI_API_KEY": ["api_keys", "ai_api_key"],
    "SMART_MEDIA_TMDB_API_KEY": ["tmdb", "api_key"],
    "SMART_MEDIA_QUARK_COOKIE": ["quark", "cookie"],
    "SMART_MEDIA_EMBY_URL": ["emby", "url"],
    "SMART_MEDIA_EMBY_PROXY_BASE_URL": ["emby", "proxy_base_url"],
    "SMART_MEDIA_EMBY_API_KEY": ["emby", "api_key"],
    "SMART_MEDIA_TELEGRAM_BOT_TOKEN": ["telegram", "bot_token"],
    "SMART_MEDIA_TELEGRAM_CHAT_ID": ["telegram", "chat_id"],
    "SMART_MEDIA_TELEGRAM_PROXY": ["telegram", "proxy"],
    "SMART_MEDIA_WEBDAV_USERNAME": ["webdav", "username"],
    "SMART_MEDIA_WEBDAV_PASSWORD": ["webdav", "password"],
    "SMART_MEDIA_ALIST_TOKEN": ["alist", "token"],
    "SMART_MEDIA_WECHAT_SEND_KEY": ["wechat", "send_key"],
    "SMART_MEDIA_SECURITY_API_KEY": ["security", "api_key"],
    "SMART_MEDIA_JWT_SECRET_KEY": ["security", "jwt_secret_key"],
    "SMART_MEDIA_LOG_FORMAT": ["log", "format"],
    "SMART_MEDIA_LOG_LEVEL": ["log_level"],
}

ENV_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")


def build_config_from_yaml(config_cls: type[ConfigModelT], path: str) -> ConfigModelT:
    data = load_yaml_config_data(path)
    return config_cls.model_validate(apply_env_overrides(data))


def build_config_from_env_overrides(config_cls: type[ConfigModelT]) -> ConfigModelT:
    data = apply_env_overrides({})
    if not data:
        return config_cls.model_validate({})
    return config_cls.model_validate(data)


def load_yaml_config_data(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump_config_to_yaml(config: BaseModel, path: str) -> None:
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(config.model_dump(), handle, allow_unicode=True, default_flow_style=False)


def apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    overridden = deepcopy(data)

    for env_key, path_keys in ENV_OVERRIDE_MAP.items():
        env_value = os.getenv(env_key)
        if env_value:
            _set_nested(overridden, path_keys, env_value)

    for provider_name in AI_PROVIDER_API_KEY_ENV_PRIORITY:
        env_value = get_provider_api_key_env_override(provider_name)
        if env_value:
            _set_ai_provider_api_key(overridden, provider_name, env_value)

    return replace_env_placeholders(overridden)


def replace_env_placeholders(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: replace_env_placeholders(value) for key, value in data.items()}
    if isinstance(data, list):
        return [replace_env_placeholders(item) for item in data]
    if not isinstance(data, str):
        return data

    replaced = data
    for match in ENV_PLACEHOLDER_PATTERN.findall(data):
        if ":-" in match:
            var_name, default_value = match.split(":-", 1)
        else:
            var_name = match
            default_value = ""

        env_value = os.getenv(var_name.strip())
        if env_value is not None:
            replaced = replaced.replace(f"${{{match}}}", env_value)
            continue
        if ":-" in match:
            replaced = replaced.replace(f"${{{match}}}", default_value)

    return replaced


def _set_nested(target: dict[str, Any], keys: list[str], value: str) -> None:
    current = target
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _set_ai_provider_api_key(target: dict[str, Any], provider_name: str, value: str) -> None:
    ai_section = target.get("ai")
    if isinstance(ai_section, dict):
        providers = ai_section.get("providers")
        if isinstance(providers, list):
            for provider in providers:
                if not isinstance(provider, dict):
                    continue
                current_name = str(provider.get("name", "")).strip().lower()
                if current_name == provider_name:
                    provider["api_key"] = value
                    return

    legacy_section = target.get(provider_name)
    if not isinstance(legacy_section, dict):
        legacy_section = {}
        target[provider_name] = legacy_section
    legacy_section["api_key"] = value
