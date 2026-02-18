"""
Notification provider configuration models.

Supports Telegram and WeChat notification channels.
"""

from typing import List

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.core.validators import validate_http_url
from app.core.constants import MAX_URL_LENGTH


def _get_decrypted_value(value: str) -> str:
    """Lazy import decryption function."""
    from app.core.encryption import get_decrypted_config_value
    return get_decrypted_config_value(value)


class TelegramConfig(BaseModel):
    """Telegram notification configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Enable Telegram notifications")
    bot_token: str = Field("", description="Telegram Bot Token", max_length=2048)
    chat_id: str = Field("", description="Chat ID to receive messages", max_length=256)
    proxy: str = Field("", description="Proxy server URL", max_length=MAX_URL_LENGTH)
    events: List[str] = Field(
        default_factory=lambda: ["task_completed", "task_failed"],
        description="Event types to push",
    )

    @field_validator("bot_token")
    @classmethod
    def validate_and_decrypt_bot_token(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, v: str) -> str:
        if v and (v.startswith("${") and v.endswith("}")):
            return v
        if v:
            validate_http_url(v, "proxy")
        return v


class WeChatConfig(BaseModel):
    """WeChat notification configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Enable WeChat notifications")
    provider: str = Field("serverchan", description="WeChat provider", max_length=256)
    send_key: str = Field("", description="SendKey", max_length=2048)


class NotificationConfig(BaseModel):
    """Aggregated notification configuration."""

    model_config = ConfigDict(extra="forbid")

    telegram: TelegramConfig = Field(
        default_factory=TelegramConfig,
        description="Telegram notification config",
    )
    wechat: WeChatConfig = Field(
        default_factory=WeChatConfig,
        description="WeChat notification config",
    )
