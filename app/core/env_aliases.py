from __future__ import annotations

import os


QUARK_COOKIE_ENV_PRIORITY = ("SMART_MEDIA_QUARK_COOKIE", "QUARK_COOKIE")
TMDB_API_KEY_ENV_PRIORITY = ("SMART_MEDIA_TMDB_API_KEY", "TMDB_API_KEY")
AI_API_KEY_ENV_PRIORITY = ("SMART_MEDIA_AI_API_KEY", "AI_API_KEY")
JWT_SECRET_KEY_ENV_PRIORITY = ("SMART_MEDIA_JWT_SECRET_KEY", "JWT_SECRET_KEY")

AI_PROVIDER_API_KEY_ENV_PRIORITY = {
    "zhipu": ("SMART_MEDIA_ZHIPU_API_KEY", "ZHIPU_API_KEY"),
    "deepseek": ("SMART_MEDIA_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"),
    "glm": ("SMART_MEDIA_GLM_API_KEY", "GLM_API_KEY"),
    "kimi": ("SMART_MEDIA_KIMI_API_KEY", "KIMI_API_KEY"),
}

AI_PROVIDER_API_KEY_ENV_MAP = {
    provider_name: env_names[0]
    for provider_name, env_names in AI_PROVIDER_API_KEY_ENV_PRIORITY.items()
}


def get_env_override(*env_names: str) -> str:
    """Return the first non-empty env value in priority order."""
    for env_name in env_names:
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
    return ""


def get_provider_api_key_env_override(provider_name: str) -> str:
    """Return provider API key from canonical env first, then legacy aliases."""
    return get_env_override(*AI_PROVIDER_API_KEY_ENV_PRIORITY.get(provider_name.lower(), ()))
