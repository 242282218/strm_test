"""
Storage provider configuration models.

Supports Quark, AList, and WebDAV storage backends.
"""

from typing import List

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.core.validators import validate_http_url
from app.core.constants import MAX_URL_LENGTH


def _get_decrypted_value(value: str) -> str:
    """Lazy import decryption function."""
    from app.core.encryption import get_decrypted_config_value
    return get_decrypted_config_value(value)


class QuarkConfig(BaseModel):
    """Quark cloud drive configuration."""

    model_config = ConfigDict(extra="forbid")

    cookie: str = Field("", description="Quark Cookie", max_length=4096)
    referer: str = Field(
        "https://pan.quark.cn/",
        description="Quark Referer",
        max_length=256,
    )
    root_id: str = Field("0", description="Quark Root ID", max_length=64)
    only_video: bool = Field(True, description="Only process video files")

    @field_validator("cookie")
    @classmethod
    def validate_and_decrypt_cookie(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v


class AListConfig(BaseModel):
    """AList configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Enable AList integration")
    url: str = Field(
        "http://localhost:5244",
        description="AList server URL",
        max_length=MAX_URL_LENGTH,
    )
    token: str = Field("", description="AList Token", max_length=2048)
    mount_path: str = Field("/", description="Quark mount path in AList")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v:
            return "http://localhost:5244"
        v = v.rstrip("/")
        validate_http_url(v, "alist.url")
        return v

    @field_validator("mount_path")
    @classmethod
    def validate_mount_path(cls, v: str) -> str:
        if not v:
            return "/"
        return v


class WebDAVConfig(BaseModel):
    """WebDAV configuration for fallback playback."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Enable WebDAV fallback")
    fallback_enabled: bool = Field(True, description="Enable auto failover")
    url: str = Field(
        "http://localhost:5244/dav",
        description="WebDAV server URL",
        max_length=MAX_URL_LENGTH,
    )
    username: str = Field("", description="WebDAV username", max_length=128)
    password: str = Field("", description="WebDAV password", max_length=256)
    mount_path: str = Field("/", description="Quark mount path in WebDAV")
    read_only: bool = Field(True, description="WebDAV read only")

    @field_validator("username")
    @classmethod
    def validate_and_decrypt_username(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v

    @field_validator("password")
    @classmethod
    def validate_and_decrypt_password(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v:
            return "http://localhost:5244/dav"
        v = v.rstrip("/")
        validate_http_url(v, "webdav.url")
        return v

    @field_validator("mount_path")
    @classmethod
    def validate_mount_path(cls, v: str) -> str:
        if not v:
            return "/"
        return v


class StorageConfig(BaseModel):
    """Aggregated storage configuration."""

    model_config = ConfigDict(extra="forbid")

    quark: QuarkConfig = Field(
        default_factory=QuarkConfig,
        description="Quark cloud drive config",
    )
    alist: AListConfig = Field(
        default_factory=AListConfig,
        description="AList config",
    )
    webdav: WebDAVConfig = Field(
        default_factory=WebDAVConfig,
        description="WebDAV config",
    )
