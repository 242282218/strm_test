"""
配置管理模块

参考: AlistAutoStrm config.go
"""

from typing import ClassVar

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config.ai_config import AIConfig
from app.config.metadata import (
    LEGACY_AI_SCHEMA_KEYS as APP_CONFIG_LEGACY_AI_SCHEMA_KEYS,
    LEGACY_AI_SENSITIVE_KEYS as APP_CONFIG_LEGACY_AI_SENSITIVE_KEYS,
    build_public_model_json_schema,
    collect_sensitive_fields_status,
)
from app.config.runtime import (
    apply_env_overrides,
    build_config_from_env_overrides,
    build_config_from_yaml,
    dump_config_to_yaml,
    replace_env_placeholders,
)
from app.core.constants import MAX_TIMEOUT_SECONDS, MAX_URL_LENGTH, MIN_TIMEOUT_SECONDS
from app.core.encryption import get_decrypted_config_value
from app.core.validators import validate_http_url


class EndpointConfig(BaseModel):
    """端点配置"""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(default="", description="OpenList/AList base URL", max_length=MAX_URL_LENGTH)
    token: str | None = Field(None, description="API token", max_length=2048)
    username: str | None = Field(None, description="Username", max_length=256)
    password: str | None = Field(None, description="Password", max_length=256)
    insecure_tls_verify: bool = Field(False, description="Skip TLS verification")
    dirs: list["DirConfig"] = Field(default_factory=list, description="Directory mappings")
    max_connections: int = Field(5, description="Max concurrent connections", ge=1, le=100)
    emby_url: str | None = Field(None, description="Emby server URL", max_length=MAX_URL_LENGTH)
    emby_api_key: str | None = Field(None, description="Emby API key", max_length=2048)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v):
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "base_url")
            return v
        return v

    @field_validator("emby_url")
    @classmethod
    def validate_emby_url(cls, v):
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "emby_url")
            return v
        return v


class DirConfig(BaseModel):
    """目录配置"""

    model_config = ConfigDict(extra="forbid")

    local_directory: str = Field(..., description="Local directory path", max_length=512)
    remote_directories: list[str] = Field(..., description="Remote directory paths", min_length=1)
    not_recursive: bool = Field(False, description="Disable recursive scan")
    create_sub_directory: bool = Field(False, description="Create subdirectories")
    disabled: bool = Field(False, description="Disable this directory")
    force_refresh: bool = Field(False, description="Force refresh")

    @field_validator("local_directory")
    @classmethod
    def validate_local_directory(cls, v):
        if not v:
            raise ValueError("local_directory cannot be empty")
        return v


class APIKeysConfig(BaseModel):
    """API 密钥配置"""

    model_config = ConfigDict(extra="forbid")

    ai_api_key: str | None = Field(None, description="AI API 密钥", max_length=2048)
    tmdb_api_key: str | None = Field(None, description="TMDB API 密钥", max_length=2048)


class TelegramConfig(BaseModel):
    """Telegram 通知配置"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用 Telegram 通知")
    bot_token: str = Field("", description="Telegram Bot Token", max_length=2048)
    chat_id: str = Field("", description="接收消息的 Chat ID", max_length=256)
    proxy: str = Field("", description="代理服务器地址", max_length=MAX_URL_LENGTH)
    events: list[str] = Field(
        default_factory=lambda: ["task_completed", "task_failed"], description="需要推送的事件类型"
    )

    @field_validator("bot_token")
    @classmethod
    def validate_and_decrypt_bot_token(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, v):
        # 如果是环境变量占位符格式，则跳过校验
        if v and (v.startswith("${") and v.endswith("}")):
            return v
        if v:
            validate_http_url(v, "proxy")
        return v


class WeChatConfig(BaseModel):
    """微信通知配置"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用微信通知")
    provider: str = Field("serverchan", description="WeChat provider", max_length=256)
    send_key: str = Field("", description="SendKey", max_length=2048)


class AListConfig(BaseModel):
    """AList 配置"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用 AList 集成")
    url: str = Field("http://localhost:5244", description="AList 服务地址", max_length=MAX_URL_LENGTH)
    token: str = Field("", description="AList Token", max_length=2048)
    mount_path: str = Field("/", description="夸克网盘在 AList 中的挂载路径")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if not v:
            return "http://localhost:5244"
        v = v.rstrip("/")
        validate_http_url(v, "alist.url")
        return v

    @field_validator("mount_path")
    @classmethod
    def validate_mount_path(cls, v):
        if not v:
            return "/"
        return v


class WebDAVConfig(BaseModel):
    """WebDAV 配置（用于兜底播放）"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用 WebDAV 兜底功能")
    fallback_enabled: bool = Field(True, description="是否启用故障自动切换")
    url: str = Field("http://localhost:5244/dav", description="WebDAV 服务地址", max_length=MAX_URL_LENGTH)
    username: str = Field("", description="WebDAV username", max_length=128)
    password: str = Field("", description="WebDAV 密码", max_length=256)
    mount_path: str = Field("/", description="夸克网盘在 WebDAV 中的挂载路径")
    read_only: bool = Field(True, description="WebDAV read only")

    @field_validator("username")
    @classmethod
    def validate_and_decrypt_username(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator("password")
    @classmethod
    def validate_and_decrypt_password(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if not v:
            return "http://localhost:5244/dav"
        v = v.rstrip("/")
        validate_http_url(v, "webdav.url")
        return v

    @field_validator("mount_path")
    @classmethod
    def validate_mount_path(cls, v):
        if not v:
            return "/"
        return v


class QuarkConfig(BaseModel):
    """夸克网盘配置"""

    model_config = ConfigDict(extra="forbid")

    cookie: str = Field("", description="Quark Cookie", max_length=4096)
    referer: str = Field("https://pan.quark.cn/", description="Quark Referer", max_length=256)
    root_id: str = Field("0", description="Quark Root ID", max_length=64)
    only_video: bool = Field(True, description="Only process video files")

    @field_validator("cookie")
    @classmethod
    def validate_and_decrypt_cookie(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class TmdbConfig(BaseModel):
    """TMDB 配置"""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="TMDB API Key", max_length=2048)

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class EmbyRefreshConfig(BaseModel):
    """Emby 刷新配置"""

    model_config = ConfigDict(extra="forbid")

    on_strm_generate: bool = Field(True, description="Trigger refresh after STRM generation")
    on_rename: bool = Field(True, description="重命名后是否触发刷新")
    cron: str | None = Field(None, description="Cron 表达式（5 或 6 字段），为空则不启用")
    library_ids: list[str] = Field(default_factory=list, description="要刷新的媒体库 ID 列表（为空则全库）")
    episode_aggregate_window_seconds: int = Field(
        10,
        description="Episode webhook 事件聚合窗口（秒）",
        ge=1,
        le=300,
    )

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v):
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
    """全局 Emby 配置"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用 Emby 集成")
    url: str = Field("", description="Emby Server URL", max_length=MAX_URL_LENGTH)
    proxy_base_url: str = Field("", description="Dedicated proxy base URL for Emby playback", max_length=MAX_URL_LENGTH)
    api_key: str = Field("", description="Emby API Key", max_length=2048)
    timeout: int = Field(
        30,
        description="Emby 请求超时（秒）",
        ge=MIN_TIMEOUT_SECONDS,
        le=MAX_TIMEOUT_SECONDS,
    )
    notify_on_complete: bool = Field(True, description="刷新完成后是否发送通知")
    delete_execute_enabled: bool = Field(False, description="是否允许执行删除联动")
    refresh: EmbyRefreshConfig = Field(default_factory=EmbyRefreshConfig, description="Emby 刷新配置")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        # 如果是环境变量占位符格式，则跳过校验
        if v and (v.startswith("${") and v.endswith("}")):
            return v
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "emby.url")
            return v
        return v

    @field_validator("proxy_base_url")
    @classmethod
    def validate_proxy_base_url(cls, v):
        if v and (v.startswith("${") and v.endswith("}")):
            return v
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "emby.proxy_base_url")
            return v
        return v

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class PlaybackRoutingConfig(BaseModel):
    """播放路由决策配置"""

    model_config = ConfigDict(extra="forbid")

    direct_first: bool = Field(True, description="是否优先尝试直链")
    force_proxy_clients: list[str] = Field(default_factory=list, description="强制走代理的客户端关键字")
    force_proxy_hosts: list[str] = Field(default_factory=list, description="强制走代理的上游 host 模式")
    sticky_downgrade_threshold: int = Field(0, description="触发粘性降级所需的连续直链失败次数", ge=0, le=100)
    sticky_downgrade_ttl_sec: int = Field(0, description="粘性降级生效时长（秒）", ge=0, le=86400)
    first_segment_cache_enabled: bool = Field(False, description="是否启用首段缓存")
    first_segment_cache_mb: int = Field(0, description="首段缓存大小（MB）", ge=0, le=64)
    first_segment_cache_ttl_sec: int = Field(0, description="首段缓存 TTL（秒）", ge=0, le=86400)


class ZhipuConfig(BaseModel):
    """智谱 AI 配置"""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="Zhipu AI API Key", max_length=2048)

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class DeepSeekConfig(BaseModel):
    """DeepSeek AI configuration"""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="DeepSeek API Key", max_length=2048)
    base_url: str = Field("https://api.deepseek.com/v1", description="DeepSeek base URL", max_length=MAX_URL_LENGTH)
    model: str = Field("deepseek-chat", description="DeepSeek model", max_length=256)
    timeout: int = Field(20, description="DeepSeek timeout in seconds", ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v):
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "deepseek.base_url")
            return v
        return "https://api.deepseek.com/v1"


class GLMConfig(BaseModel):
    """GLM (Zhipu) AI configuration"""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="GLM API Key", max_length=2048)
    base_url: str = Field("https://open.bigmodel.cn/api/paas/v4", description="GLM base URL", max_length=MAX_URL_LENGTH)
    model: str = Field("glm-4.7-flash", description="GLM model", max_length=256)
    timeout: int = Field(8, description="GLM timeout in seconds", ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v):
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "glm.base_url")
            return v
        return "https://open.bigmodel.cn/api/paas/v4"


class KimiConfig(BaseModel):
    """Kimi (NVIDIA OpenAI-compatible) configuration"""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="Kimi API Key", max_length=2048)
    base_url: str = Field("https://integrate.api.nvidia.com/v1", description="Kimi base URL", max_length=MAX_URL_LENGTH)
    model: str = Field("moonshotai/kimi-k2.5", description="Kimi model", max_length=256)
    timeout: int = Field(15, description="Kimi timeout in seconds", ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v):
        if v:
            v = v.rstrip("/")
            validate_http_url(v, "kimi.base_url")
            return v
        return "https://integrate.api.nvidia.com/v1"


class CorsConfig(BaseModel):
    """CORS settings"""

    model_config = ConfigDict(extra="forbid")

    allow_origins: list[str] = Field(default_factory=list, description="Allowed origins")
    allow_credentials: bool = Field(False, description="Allow credentials")
    allow_methods: list[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"], description="Allowed methods")
    allow_headers: list[str] = Field(default_factory=lambda: ["Authorization", "Content-Type", "X-Requested-With"], description="Allowed headers")

    @model_validator(mode="after")
    def validate_cors_config(self):
        """Validate CORS configuration for production safety."""
        import os
        env = os.getenv("ENVIRONMENT", "development")

        if env == "production":
            if "*" in self.allow_origins:
                from app.core.logging import get_logger
                logger = get_logger(__name__)
                logger.warning(
                    "CORS allow_origins contains '*' in production environment. "
                    "This is not recommended for security reasons. "
                    "Please configure specific allowed origins."
                )

            if self.allow_credentials and "*" in self.allow_origins:
                raise ValueError(
                    "CORS allow_credentials cannot be True when allow_origins contains '*' "
                    "due to browser security restrictions."
                )

        return self


class SecurityConfig(BaseModel):
    """Security settings"""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="API key for protected endpoints", max_length=2048)
    require_api_key: bool = Field(True, description="Require API key for protected endpoints")
    jwt_secret_key: str = Field("", description="JWT secret key for signing tokens", max_length=2048)

    @field_validator("api_key")
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class LogConfig(BaseModel):
    """日志配置"""

    model_config = ConfigDict(extra="forbid")

    format: str = Field("text", description="Log format: text or json")
    include_timestamp: bool = Field(True, description="Include timestamp in logs")
    include_level: bool = Field(True, description="Include log level in logs")
    include_request_id: bool = Field(True, description="Include request ID in logs")
    include_source: bool = Field(True, description="Include source location (file:line) in logs")
    json_indent: int | None = Field(None, description="JSON indent for pretty printing (None for compact)")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        valid_formats = ["text", "json"]
        if v.lower() not in valid_formats:
            raise ValueError(f"log format must be one of {valid_formats}")
        return v.lower()


class AppConfig(BaseModel):
    """应用配置"""

    LEGACY_AI_SCHEMA_KEYS: ClassVar[set[str]] = APP_CONFIG_LEGACY_AI_SCHEMA_KEYS
    LEGACY_AI_SENSITIVE_KEYS: ClassVar[set[str]] = APP_CONFIG_LEGACY_AI_SENSITIVE_KEYS


    model_config = ConfigDict(extra="forbid")

    database: str = Field("quark_strm.db", description="Database file path", max_length=512)
    endpoints: list[EndpointConfig] = Field(default_factory=list, description="Endpoint configurations")
    log_level: str = Field("INFO", description="Log level")
    log_file: str | None = Field(None, description="Log file path")
    colored_log: bool = Field(True, description="Enable colored logs")
    log: LogConfig = Field(default_factory=LogConfig, description="Log configuration")
    timeout: int = Field(30, description="Request timeout in seconds", ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)
    exts: list[str] = Field(default_factory=lambda: [".mp4", ".mkv", ".avi", ".mov"], description="Video extensions")
    alt_exts: list[str] = Field(default_factory=lambda: [".srt", ".ass"], description="Subtitle extensions")
    create_sub_directory: bool = Field(False, description="Create subdirectories globally")
    api_keys: APIKeysConfig | None = Field(None, description="API 密钥配置")
    telegram: TelegramConfig = Field(default_factory=TelegramConfig, description="Telegram 通知配置")
    wechat: WeChatConfig = Field(default_factory=WeChatConfig, description="微信通知配置")
    webdav: WebDAVConfig = Field(default_factory=WebDAVConfig, description="WebDAV 配置")
    alist: AListConfig = Field(default_factory=AListConfig, description="AList 配置")

    # 新增字段
    quark: QuarkConfig = Field(default_factory=QuarkConfig, description="夸克网盘配置")
    tmdb: TmdbConfig = Field(default_factory=TmdbConfig, description="TMDB 配置")
    emby: GlobalEmbyConfig = Field(default_factory=GlobalEmbyConfig, description="Emby 配置")
    playback: PlaybackRoutingConfig = Field(default_factory=PlaybackRoutingConfig, description="播放路由配置")

    # 统一 AI 配置（推荐）
    ai: AIConfig | None = Field(None, description="Unified AI configuration (OpenAI compatible)")

    cors: CorsConfig = Field(default_factory=CorsConfig, description="CORS settings")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Security settings")

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        ai_section = normalized.get("ai")
        if isinstance(ai_section, dict):
            unified_ai_keys = {"providers", "max_retries", "fallback_enabled"}
            if not unified_ai_keys.intersection(ai_section.keys()) and "api_key" in ai_section:
                normalized["zhipu"] = normalized.pop("ai")

        providers_section: list[dict] = []
        current_ai = normalized.get("ai")
        if isinstance(current_ai, dict) and isinstance(current_ai.get("providers"), list):
            providers_section = [item for item in current_ai["providers"] if isinstance(item, dict)]
            normalized["ai"] = dict(current_ai)
        else:
            normalized["ai"] = {}

        existing_names = {
            str(item.get("name")).strip()
            for item in providers_section
            if str(item.get("name", "")).strip()
        }

        legacy_sections = [
            ("deepseek", normalized.pop("deepseek", None), {
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "timeout": 20,
            }),
            ("glm", normalized.pop("glm", None), {
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model": "glm-4.7-flash",
                "timeout": 8,
            }),
            ("kimi", normalized.pop("kimi", None), {
                "base_url": "https://integrate.api.nvidia.com/v1",
                "model": "moonshotai/kimi-k2.5",
                "timeout": 15,
            }),
            ("zhipu", normalized.pop("zhipu", None), {
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model": "glm-4.7-flash",
                "timeout": 8,
            }),
        ]

        priority = 100 - len(providers_section) * 10
        for name, section, defaults in legacy_sections:
            if name in existing_names or not isinstance(section, dict):
                continue
            api_key = str(section.get("api_key", "")).strip()
            if not api_key:
                continue
            providers_section.append({
                "name": name,
                "api_key": api_key,
                "base_url": section.get("base_url") or defaults["base_url"],
                "model": section.get("model") or defaults["model"],
                "timeout": section.get("timeout") or defaults["timeout"],
                "priority": priority,
            })
            priority -= 10

        if providers_section:
            normalized["ai"]["providers"] = providers_section

        return normalized

    @field_validator("api_keys", mode="before")
    @classmethod
    def normalize_api_keys(cls, v):
        return v or {}

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()

    @model_validator(mode="after")
    def validate_enabled_configs(self):
        if self.telegram.enabled:
            if not self.telegram.bot_token or not self.telegram.chat_id:
                raise ValueError("Telegram enabled but bot_token/chat_id missing")
        if self.webdav.enabled:
            if not self.webdav.username or not self.webdav.password:
                raise ValueError("WebDAV enabled but username/password missing")
        return self

    @classmethod
    def from_yaml(cls, path: str) -> "AppConfig":
        return build_config_from_yaml(cls, path)

    @classmethod
    def from_env_overrides(cls) -> "AppConfig":
        return build_config_from_env_overrides(cls)

    @classmethod
    def _apply_env_overrides(cls, data: dict) -> dict:
        return apply_env_overrides(data)

    @classmethod
    def _replace_env_placeholders(cls, data: any) -> any:
        return replace_env_placeholders(data)

    def to_yaml(self, path: str) -> None:
        dump_config_to_yaml(self, path)

    def validate_required_configs(self) -> list[str]:
        """
        Validate that required configurations are present.
        Returns a list of missing configuration warnings.
        """
        warnings = []

        # Check Telegram if enabled
        if self.telegram.enabled:
            if not self.telegram.bot_token:
                warnings.append("Telegram is enabled but bot_token is not set (set SMART_MEDIA_TELEGRAM_BOT_TOKEN)")
            if not self.telegram.chat_id:
                warnings.append("Telegram is enabled but chat_id is not set (set SMART_MEDIA_TELEGRAM_CHAT_ID)")

        # Check WebDAV if enabled
        if self.webdav.enabled:
            if not self.webdav.username:
                warnings.append("WebDAV is enabled but username is not set (set SMART_MEDIA_WEBDAV_USERNAME)")
            if not self.webdav.password:
                warnings.append("WebDAV is enabled but password is not set (set SMART_MEDIA_WEBDAV_PASSWORD)")

        # Check Emby if enabled
        if self.emby.enabled:
            if not self.emby.url:
                warnings.append("Emby is enabled but url is not set (set SMART_MEDIA_EMBY_URL)")
            if not self.emby.api_key:
                warnings.append("Emby is enabled but api_key is not set (set SMART_MEDIA_EMBY_API_KEY)")

        # Check AList if enabled
        if self.alist.enabled:
            if not self.alist.token:
                warnings.append("AList is enabled but token is not set (set SMART_MEDIA_ALIST_TOKEN)")

        # Check WeChat if enabled
        if self.wechat.enabled:
            if not self.wechat.send_key:
                warnings.append("WeChat is enabled but send_key is not set (set SMART_MEDIA_WECHAT_SEND_KEY)")

        # Check security if API key required
        if self.security.require_api_key and not self.security.api_key:
            warnings.append("API key is required but security.api_key is not set (set SMART_MEDIA_SECURITY_API_KEY)")

        return warnings

    @classmethod
    def public_model_json_schema(cls) -> dict:
        return build_public_model_json_schema(cls)

    def get_sensitive_fields_status(self) -> dict[str, bool]:
        return collect_sensitive_fields_status(self)
