"""
Media service configuration models.

Supports TMDB and Emby integration.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from app.core.validators import validate_http_url
from app.core.constants import MAX_URL_LENGTH, MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS
from apscheduler.triggers.cron import CronTrigger


def _get_decrypted_value(value: str) -> str:
    """Lazy import decryption function."""
    from app.core.encryption import get_decrypted_config_value
    return get_decrypted_config_value(value)


class TmdbConfig(BaseModel):
    """TMDB configuration."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="TMDB API Key", max_length=2048)

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v


class EmbyRefreshConfig(BaseModel):
    """Emby refresh configuration."""

    model_config = ConfigDict(extra="forbid")

    on_strm_generate: bool = Field(
        True,
        description="Trigger refresh after STRM generation",
    )
    on_rename: bool = Field(True, description="Trigger refresh after rename")
    cron: Optional[str] = Field(
        None,
        description="Cron expression (5 or 6 fields), empty to disable",
    )
    library_ids: List[str] = Field(
        default_factory=list,
        description="Library IDs to refresh (empty for all)",
    )
    episode_aggregate_window_seconds: int = Field(
        10,
        description="Episode webhook event aggregation window (seconds)",
        ge=1,
        le=300,
    )

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        if not v:
            return None
        fields = v.split()
        if len(fields) == 6:
            CronTrigger(
                second=fields[0],
                minute=fields[1],
                hour=fields[2],
                day=fields[3],
                month=fields[4],
                day_of_week=fields[5],
            )
            return v
        if len(fields) == 5:
            CronTrigger.from_crontab(v)
            return v
        raise ValueError("emby.refresh.cron must have 5 or 6 fields")


class GlobalEmbyConfig(BaseModel):
    """Global Emby configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Enable Emby integration")
    url: str = Field("", description="Emby Server URL", max_length=MAX_URL_LENGTH)
    api_key: str = Field("", description="Emby API Key", max_length=2048)
    timeout: int = Field(
        30,
        description="Emby request timeout (seconds)",
        ge=MIN_TIMEOUT_SECONDS,
        le=MAX_TIMEOUT_SECONDS,
    )
    notify_on_complete: bool = Field(
        True,
        description="Send notification after refresh",
    )
    delete_execute_enabled: bool = Field(
        False,
        description="Allow delete linkage execution",
    )
    refresh: EmbyRefreshConfig = Field(
        default_factory=EmbyRefreshConfig,
        description="Emby refresh config",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if v and (v.startswith("${") and v.endswith("}")):
            return v
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "emby.url")
        return v

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v: str) -> str:
        if v and v.startswith("encrypted:"):
            return _get_decrypted_value(v)
        return v


class MediaConfig(BaseModel):
    """Aggregated media configuration."""

    model_config = ConfigDict(extra="forbid")

    tmdb: TmdbConfig = Field(default_factory=TmdbConfig, description="TMDB config")
    emby: GlobalEmbyConfig = Field(
        default_factory=GlobalEmbyConfig,
        description="Emby config",
    )

    @model_validator(mode="after")
    def validate_enabled_configs(self) -> "MediaConfig":
        if self.emby.enabled:
            errors = []
            if not self.emby.url:
                errors.append("Emby enabled but url missing")
            if not self.emby.api_key:
                errors.append("Emby enabled but api_key missing")
            if errors:
                raise ValueError("; ".join(errors))
        return self
