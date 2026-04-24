from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.config.settings import AppConfig
from app.core import config_manager as config_manager_module
from app.core.config_manager import ConfigManager
from app.core import dependencies as dependencies_module
from app.services import config_service as config_service_module
from app.services import auth_service as auth_service_module
from app.services.config_service import ConfigService


def _write_config(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _reset_config_singletons() -> None:
    ConfigService._instance = None
    config_service_module._config_service_instance = None
    ConfigManager._instance = None
    ConfigManager._config = None
    config_manager_module._config_manager_instance = None


@pytest.mark.asyncio
async def test_get_quark_cookie_prefers_canonical_env_over_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMART_MEDIA_QUARK_COOKIE", "canonical-cookie")
    monkeypatch.setenv("QUARK_COOKIE", "legacy-cookie")

    with patch.object(
        dependencies_module,
        "_get_runtime_quark_config",
        return_value=SimpleNamespace(cookie="config-cookie"),
    ):
        cookie = await dependencies_module.get_quark_cookie()

    assert cookie == "canonical-cookie"


@pytest.mark.asyncio
async def test_get_quark_cookie_keeps_legacy_env_as_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMART_MEDIA_QUARK_COOKIE", raising=False)
    monkeypatch.setenv("QUARK_COOKIE", "legacy-cookie")

    with patch.object(
        dependencies_module,
        "_get_runtime_quark_config",
        return_value=SimpleNamespace(cookie="config-cookie"),
    ):
        cookie = await dependencies_module.get_quark_cookie()

    assert cookie == "legacy-cookie"


def test_get_jwt_secret_key_prefers_canonical_env_over_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    original_secret = auth_service_module.JWT_SECRET_KEY
    auth_service_module.JWT_SECRET_KEY = ""
    monkeypatch.setenv("SMART_MEDIA_JWT_SECRET_KEY", "canonical-secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "legacy-secret")

    try:
        with patch("app.services.config_service.get_config_service") as mock_get_config_service:
            mock_get_config_service.return_value.get_config.return_value = SimpleNamespace(
                security=SimpleNamespace(jwt_secret_key="config-secret")
            )
            secret = auth_service_module._get_jwt_secret_key()
    finally:
        auth_service_module.JWT_SECRET_KEY = original_secret

    assert secret == "canonical-secret"


def test_get_jwt_secret_key_keeps_legacy_env_as_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    original_secret = auth_service_module.JWT_SECRET_KEY
    auth_service_module.JWT_SECRET_KEY = ""
    monkeypatch.delenv("SMART_MEDIA_JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "legacy-secret")

    try:
        secret = auth_service_module._get_jwt_secret_key()
    finally:
        auth_service_module.JWT_SECRET_KEY = original_secret

    assert secret == "legacy-secret"


def test_app_config_from_yaml_applies_provider_env_to_unified_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """
ai:
  providers:
    - name: deepseek
      api_key: ""
      base_url: "https://api.deepseek.com/v1"
      model: "deepseek-chat"
      timeout: 20
""".strip(),
    )
    monkeypatch.setenv("SMART_MEDIA_DEEPSEEK_API_KEY", "env-deepseek-key")

    config = AppConfig.from_yaml(str(config_path))

    provider = next(provider for provider in config.ai.providers if provider.name == "deepseek")
    assert provider.api_key == "env-deepseek-key"


def test_app_config_from_yaml_applies_provider_env_to_legacy_ai_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """
glm:
  api_key: ""
  base_url: "https://open.bigmodel.cn/api/paas/v4"
  model: "glm-4.7-flash"
  timeout: 8
""".strip(),
    )
    monkeypatch.setenv("SMART_MEDIA_GLM_API_KEY", "env-glm-key")

    config = AppConfig.from_yaml(str(config_path))

    provider = next(provider for provider in config.ai.providers if provider.name == "glm")
    assert provider.api_key == "env-glm-key"


def test_app_config_from_yaml_prefers_canonical_provider_env_over_legacy_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """
deepseek:
  api_key: ""
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  timeout: 20
""".strip(),
    )
    monkeypatch.setenv("SMART_MEDIA_DEEPSEEK_API_KEY", "canonical-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-deepseek-key")

    config = AppConfig.from_yaml(str(config_path))

    provider = next(provider for provider in config.ai.providers if provider.name == "deepseek")
    assert provider.api_key == "canonical-deepseek-key"


def test_app_config_from_yaml_keeps_legacy_provider_env_as_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """
kimi:
  api_key: ""
  base_url: "https://integrate.api.nvidia.com/v1"
  model: "moonshotai/kimi-k2.5"
  timeout: 15
""".strip(),
    )
    monkeypatch.delenv("SMART_MEDIA_KIMI_API_KEY", raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "legacy-kimi-key")

    config = AppConfig.from_yaml(str(config_path))

    provider = next(provider for provider in config.ai.providers if provider.name == "kimi")
    assert provider.api_key == "legacy-kimi-key"


def test_config_service_applies_provider_env_overrides_without_config_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "missing-config.yaml"
    monkeypatch.setenv("SMART_MEDIA_DEEPSEEK_API_KEY", "canonical-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-deepseek-key")
    _reset_config_singletons()

    try:
        service = ConfigService(str(config_path))
        provider = next(provider for provider in service.get_config().ai.providers if provider.name == "deepseek")
    finally:
        _reset_config_singletons()

    assert provider.api_key == "canonical-deepseek-key"


def test_config_manager_applies_legacy_provider_env_without_config_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "missing-config.yaml"
    monkeypatch.delenv("SMART_MEDIA_GLM_API_KEY", raising=False)
    monkeypatch.setenv("GLM_API_KEY", "legacy-glm-key")
    _reset_config_singletons()

    try:
        manager = ConfigManager(str(config_path))
        providers = manager.get("ai.providers", [])
    finally:
        _reset_config_singletons()

    provider = next(provider for provider in providers if provider["name"] == "glm")
    assert provider["api_key"] == "legacy-glm-key"


def test_env_example_documents_canonical_env_contract_only() -> None:
    env_example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    documented_envs = {
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }

    canonical_envs = (
        "SMART_MEDIA_QUARK_COOKIE",
        "SMART_MEDIA_JWT_SECRET_KEY",
        "SMART_MEDIA_ZHIPU_API_KEY",
        "SMART_MEDIA_DEEPSEEK_API_KEY",
        "SMART_MEDIA_GLM_API_KEY",
        "SMART_MEDIA_KIMI_API_KEY",
    )
    legacy_envs = (
        "QUARK_COOKIE",
        "JWT_SECRET_KEY",
        "ZHIPU_API_KEY",
        "DEEPSEEK_API_KEY",
        "GLM_API_KEY",
        "KIMI_API_KEY",
    )

    for env_name in canonical_envs:
        assert env_name in documented_envs
    for env_name in legacy_envs:
        assert env_name not in documented_envs


def test_config_example_documents_canonical_env_comments() -> None:
    config_example = (Path(__file__).resolve().parents[1] / "config.example.yaml").read_text(encoding="utf-8")

    documented_envs = (
        "SMART_MEDIA_QUARK_COOKIE",
        "SMART_MEDIA_JWT_SECRET_KEY",
        "SMART_MEDIA_ZHIPU_API_KEY",
        "SMART_MEDIA_DEEPSEEK_API_KEY",
        "SMART_MEDIA_GLM_API_KEY",
        "SMART_MEDIA_KIMI_API_KEY",
    )

    for env_name in documented_envs:
        assert f"Environment: {env_name}" in config_example
