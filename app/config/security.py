"""
Security and CORS configuration models.
"""

from typing import List

from pydantic import BaseModel, Field, field_validator, ConfigDict


def _get_decrypted_value(value: str) -> str:
    """Lazy import decryption function."""
    from app.core.encryption import get_decrypted_config_value
    return get_decrypted_config_value(value)


class CorsConfig(BaseModel):
    """CORS settings."""

    model_config = ConfigDict(extra="forbid")

    allow_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed origins",
    )
    allow_credentials: bool = Field(False, description="Allow credentials")
    allow_methods: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed methods",
    )
    allow_headers: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed headers",
    )


class SecurityConfig(BaseModel):
    """Security settings."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(
        "",
        description="API key for protected endpoints",
        max_length=2048,
    )
    require_api_key: bool = Field(
        True,
        description="Require API key for protected endpoints",
    )

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v


class APIKeysConfig(BaseModel):
    """API keys configuration."""

    model_config = ConfigDict(extra="forbid")

    ai_api_key: str | None = Field(None, description="AI API key", max_length=2048)
    tmdb_api_key: str | None = Field(None, description="TMDB API key", max_length=2048)
