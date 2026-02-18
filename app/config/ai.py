"""
AI provider configuration models.

Provides unified configuration interface for multiple AI providers.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.core.validators import validate_http_url
from app.core.constants import MAX_URL_LENGTH, MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS


def _get_decrypted_value(value: str) -> str:
    """Lazy import decryption function."""
    from app.core.encryption import get_decrypted_config_value
    return get_decrypted_config_value(value)


class BaseAIConfig(BaseModel):
    """Base configuration for AI providers."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="API Key", max_length=2048)
    base_url: str = Field("", description="Base URL", max_length=MAX_URL_LENGTH)
    model: str = Field("", description="Model name", max_length=256)
    timeout: int = Field(
        30,
        description="Request timeout in seconds",
        ge=MIN_TIMEOUT_SECONDS,
        le=MAX_TIMEOUT_SECONDS,
    )

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "base_url")
        return v


class DeepSeekConfig(BaseAIConfig):
    """DeepSeek AI configuration."""

    base_url: str = Field(
        "https://api.deepseek.com/v1",
        description="DeepSeek base URL",
        max_length=MAX_URL_LENGTH,
    )
    model: str = Field("deepseek-chat", description="DeepSeek model", max_length=256)
    timeout: int = Field(20, description="DeepSeek timeout in seconds")


class GLMConfig(BaseAIConfig):
    """GLM (Zhipu) AI configuration."""

    base_url: str = Field(
        "https://open.bigmodel.cn/api/paas/v4",
        description="GLM base URL",
        max_length=MAX_URL_LENGTH,
    )
    model: str = Field("glm-4.7-flash", description="GLM model", max_length=256)
    timeout: int = Field(8, description="GLM timeout in seconds")


class KimiConfig(BaseAIConfig):
    """Kimi (NVIDIA OpenAI-compatible) configuration."""

    base_url: str = Field(
        "https://integrate.api.nvidia.com/v1",
        description="Kimi base URL",
        max_length=MAX_URL_LENGTH,
    )
    model: str = Field("moonshotai/kimi-k2.5", description="Kimi model", max_length=256)
    timeout: int = Field(15, description="Kimi timeout in seconds")


class ZhipuConfig(BaseModel):
    """Zhipu AI configuration (legacy)."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="Zhipu AI API Key", max_length=2048)

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v


class AIConfig(BaseModel):
    """Aggregated AI configuration."""

    model_config = ConfigDict(extra="forbid")

    zhipu: ZhipuConfig = Field(default_factory=ZhipuConfig, description="Zhipu AI config")
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig, description="DeepSeek config")
    glm: GLMConfig = Field(default_factory=GLMConfig, description="GLM config")
    kimi: KimiConfig = Field(default_factory=KimiConfig, description="Kimi config")
