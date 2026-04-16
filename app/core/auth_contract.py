"""
Shared authentication contract helpers.
"""

from __future__ import annotations

import os
from collections.abc import Callable


SecurityConfigLoader = Callable[[], tuple[str | None, bool | None]]


CANONICAL_API_KEY_ENV = "SMART_MEDIA_SECURITY_API_KEY"
LEGACY_API_KEY_ENVS = ("SMART_MEDIA_API_KEY", "API_KEY")
API_KEY_ENV_PRIORITY = (CANONICAL_API_KEY_ENV, *LEGACY_API_KEY_ENVS)
REQUIRE_API_KEY_ENV = "REQUIRE_API_KEY"
_TRUTHY_VALUES = {"true", "1", "yes"}
_FALSY_VALUES = {"false", "0", "no"}


def get_api_key_env_override() -> str | None:
    """Return the first configured API key override from env aliases."""
    for env_name in API_KEY_ENV_PRIORITY:
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
    return None


def get_require_api_key_env_override() -> bool | None:
    """Return explicit auth-required env override when configured."""
    raw_value = os.getenv(REQUIRE_API_KEY_ENV, "").strip().lower()
    if raw_value in _TRUTHY_VALUES:
        return True
    if raw_value in _FALSY_VALUES:
        return False
    return None


def resolve_expected_api_key(load_config_api_key: Callable[[], str | None]) -> str | None:
    """Resolve API key from canonical env aliases before config fallback."""
    env_key = get_api_key_env_override()
    if env_key:
        return env_key
    return load_config_api_key()


def resolve_auth_configuration(load_security_config: SecurityConfigLoader) -> tuple[str | None, bool]:
    """Resolve effective API key and auth-required flag from env/config sources."""
    config_api_key, config_require_api_key = load_security_config()
    expected_api_key = get_api_key_env_override() or config_api_key

    auth_required_override = get_require_api_key_env_override()
    if auth_required_override is not None:
        return expected_api_key, auth_required_override

    if expected_api_key:
        return expected_api_key, True

    return expected_api_key, bool(config_require_api_key)
