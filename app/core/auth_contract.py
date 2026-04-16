"""
Shared authentication contract helpers.
"""

from __future__ import annotations

import os
from typing import Callable


CANONICAL_API_KEY_ENV = "SMART_MEDIA_SECURITY_API_KEY"
LEGACY_API_KEY_ENVS = ("SMART_MEDIA_API_KEY", "API_KEY")
API_KEY_ENV_PRIORITY = (CANONICAL_API_KEY_ENV, *LEGACY_API_KEY_ENVS)


def get_api_key_env_override() -> str | None:
    """Return the first configured API key override from env aliases."""
    for env_name in API_KEY_ENV_PRIORITY:
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
    return None


def resolve_expected_api_key(load_config_api_key: Callable[[], str | None]) -> str | None:
    """Resolve API key from canonical env aliases before config fallback."""
    env_key = get_api_key_env_override()
    if env_key:
        return env_key
    return load_config_api_key()
