"""
閰嶇疆绠＄悊妯″潡

鍙傝€? AlistAutoStrm config.go
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import List, Optional
import yaml
import os
from app.core.validators import validate_http_url
from app.core.constants import MAX_URL_LENGTH, MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS
from app.core.encryption import get_decrypted_config_value
from apscheduler.triggers.cron import CronTrigger


class EndpointConfig(BaseModel):
    """绔偣閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(default="", description="OpenList/AList base URL", max_length=MAX_URL_LENGTH)
    token: Optional[str] = Field(None, description="API token", max_length=2048)
    username: Optional[str] = Field(None, description="Username", max_length=256)
    password: Optional[str] = Field(None, description="Password", max_length=256)
    insecure_tls_verify: bool = Field(False, description="Skip TLS verification")
    dirs: List['DirConfig'] = Field(default_factory=list, description="Directory mappings")
    max_connections: int = Field(5, description="Max concurrent connections", ge=1, le=100)
    emby_url: Optional[str] = Field(None, description="Emby server URL", max_length=MAX_URL_LENGTH)
    emby_api_key: Optional[str] = Field(None, description="Emby API key", max_length=2048)

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if v:
            v = v.rstrip('/')
            validate_http_url(v, "base_url")
            return v
        return v

    @field_validator('emby_url')
    @classmethod
    def validate_emby_url(cls, v):
        if v:
            v = v.rstrip('/')
            validate_http_url(v, "emby_url")
            return v
        return v


class DirConfig(BaseModel):
    """鐩綍閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    local_directory: str = Field(..., description="Local directory path", max_length=512)
    remote_directories: List[str] = Field(..., description="Remote directory paths", min_length=1)
    not_recursive: bool = Field(False, description="Disable recursive scan")
    create_sub_directory: bool = Field(False, description="Create subdirectories")
    disabled: bool = Field(False, description="Disable this directory")
    force_refresh: bool = Field(False, description="Force refresh")

    @field_validator('local_directory')
    @classmethod
    def validate_local_directory(cls, v):
        if not v:
            raise ValueError('local_directory cannot be empty')
        return v


class APIKeysConfig(BaseModel):
    """API瀵嗛挜閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    ai_api_key: Optional[str] = Field(None, description="AI API瀵嗛挜", max_length=2048)
    tmdb_api_key: Optional[str] = Field(None, description="TMDB API瀵嗛挜", max_length=2048)


class TelegramConfig(BaseModel):
    """Telegram閫氱煡閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="鏄惁鍚敤Telegram閫氱煡")
    bot_token: str = Field("", description="Telegram Bot Token", max_length=2048)
    chat_id: str = Field("", description="鎺ユ敹娑堟伅鐨凜hat ID", max_length=256)
    proxy: str = Field("", description="浠ｇ悊鏈嶅姟鍣ㄥ湴鍧€", max_length=MAX_URL_LENGTH)
    events: List[str] = Field(
        default_factory=lambda: ["task_completed", "task_failed"],
        description="闇€瑕佹帹閫佺殑浜嬩欢绫诲瀷"
    )

    @field_validator('bot_token')
    @classmethod
    def validate_and_decrypt_bot_token(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator('proxy')
    @classmethod
    def validate_proxy(cls, v):
        # 濡傛灉鏄幆澧冨彉閲忓崰浣嶇鏍煎紡锛屽垯璺宠繃楠岃瘉
        if v and (v.startswith('${') and v.endswith('}')):
            return v
        if v:
            validate_http_url(v, "proxy")
        return v


class WeChatConfig(BaseModel):
    """寰俊閫氱煡閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="鏄惁鍚敤寰俊閫氱煡")
    provider: str = Field("serverchan", description="WeChat provider", max_length=256)
    send_key: str = Field("", description="SendKey", max_length=2048)



class AListConfig(BaseModel):
    """AList閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="鏄惁鍚敤AList闆嗘垚")
    url: str = Field("http://localhost:5244", description="AList鏈嶅姟鍦板潃", max_length=MAX_URL_LENGTH)
    token: str = Field("", description="AList Token", max_length=2048)
    mount_path: str = Field("/", description="澶稿厠缃戠洏鍦ˋList涓殑鎸傝浇璺緞")

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v:
            return "http://localhost:5244"
        v = v.rstrip('/')
        validate_http_url(v, "alist.url")
        return v
    
    @field_validator('mount_path')
    @classmethod
    def validate_mount_path(cls, v):
        if not v:
            return "/"
        return v


class WebDAVConfig(BaseModel):
    """WebDAV閰嶇疆锛堢敤浜庡厹搴曟挱鏀撅級"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="鏄惁鍚敤WebDAV鍏滃簳鍔熻兘")
    fallback_enabled: bool = Field(True, description="鏄惁鍚敤鏁呴殰鑷姩鍒囨崲")
    url: str = Field("http://localhost:5244/dav", description="WebDAV鏈嶅姟鍦板潃", max_length=MAX_URL_LENGTH)
    username: str = Field("", description="WebDAV username", max_length=128)
    password: str = Field("", description="WebDAV瀵嗙爜", max_length=256)
    mount_path: str = Field("/", description="澶稿厠缃戠洏鍦╓ebDAV涓殑鎸傝浇璺緞")
    read_only: bool = Field(True, description="WebDAV read only")

    @field_validator('username')
    @classmethod
    def validate_and_decrypt_username(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator('password')
    @classmethod
    def validate_and_decrypt_password(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v:
            return "http://localhost:5244/dav"
        v = v.rstrip('/')
        validate_http_url(v, "webdav.url")
        return v

    @field_validator('mount_path')
    @classmethod
    def validate_mount_path(cls, v):
        if not v:
            return "/"
        return v



class QuarkConfig(BaseModel):
    """澶稿厠缃戠洏閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    cookie: str = Field("", description="Quark Cookie", max_length=4096)
    referer: str = Field("https://pan.quark.cn/", description="Quark Referer", max_length=256)
    root_id: str = Field("0", description="Quark Root ID", max_length=64)
    only_video: bool = Field(True, description="Only process video files")

    @field_validator('cookie')
    @classmethod
    def validate_and_decrypt_cookie(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class TmdbConfig(BaseModel):
    """TMDB閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="TMDB API Key", max_length=2048)

    @field_validator('api_key')
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class EmbyRefreshConfig(BaseModel):
    """Emby鍒锋柊閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    on_strm_generate: bool = Field(True, description="Trigger refresh after STRM generation")
    on_rename: bool = Field(True, description="閲嶅懡鍚嶅悗鏄惁瑙﹀彂鍒锋柊")
    cron: Optional[str] = Field(None, description="Cron琛ㄨ揪寮?5鎴?瀛楁)锛岀┖鍒欎笉鍚敤")
    library_ids: List[str] = Field(default_factory=list, description="瑕佸埛鏂扮殑濯掍綋搴揑D鍒楄〃(绌哄垯鍏ㄥ簱)")

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
    """鍏ㄥ眬Emby閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="鏄惁鍚敤Emby闆嗘垚")
    url: str = Field("", description="Emby Server URL", max_length=MAX_URL_LENGTH)
    api_key: str = Field("", description="Emby API Key", max_length=2048)
    timeout: int = Field(
        30,
        description="Emby璇锋眰瓒呮椂(绉?",
        ge=MIN_TIMEOUT_SECONDS,
        le=MAX_TIMEOUT_SECONDS,
    )
    notify_on_complete: bool = Field(True, description="鍒锋柊瀹屾垚鍚庢槸鍚﹀彂閫侀€氱煡")
    refresh: EmbyRefreshConfig = Field(default_factory=EmbyRefreshConfig, description="Emby鍒锋柊閰嶇疆")

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        # 濡傛灉鏄幆澧冨彉閲忓崰浣嶇鏍煎紡锛屽垯璺宠繃楠岃瘉
        if v and (v.startswith('${') and v.endswith('}')):
            return v
        if v:
            v = v.rstrip('/')
            validate_http_url(v, "emby.url")
            return v
        return v

    @field_validator('api_key')
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class ZhipuConfig(BaseModel):
    """鏅鸿氨AI閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="Zhipu AI API Key", max_length=2048)

    @field_validator('api_key')
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

    @field_validator('api_key')
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if v:
            v = v.rstrip('/')
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

    @field_validator('api_key')
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if v:
            v = v.rstrip('/')
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

    @field_validator('api_key')
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if v:
            v = v.rstrip('/')
            validate_http_url(v, "kimi.base_url")
            return v
        return "https://integrate.api.nvidia.com/v1"


class CorsConfig(BaseModel):
    """CORS settings"""
    model_config = ConfigDict(extra="forbid")

    allow_origins: List[str] = Field(default_factory=lambda: ["*"], description="Allowed origins")
    allow_credentials: bool = Field(False, description="Allow credentials")
    allow_methods: List[str] = Field(default_factory=lambda: ["*"], description="Allowed methods")
    allow_headers: List[str] = Field(default_factory=lambda: ["*"], description="Allowed headers")


class SecurityConfig(BaseModel):
    """Security settings"""
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="API key for protected endpoints", max_length=2048)
    require_api_key: bool = Field(False, description="Require API key for protected endpoints")

    @field_validator('api_key')
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class AppConfig(BaseModel):
    """搴旂敤閰嶇疆"""
    model_config = ConfigDict(extra="forbid")

    database: str = Field("quark_strm.db", description="Database file path", max_length=512)
    endpoints: List[EndpointConfig] = Field(default_factory=list, description="Endpoint configurations")
    log_level: str = Field("INFO", description="Log level")
    log_file: Optional[str] = Field(None, description="Log file path")
    colored_log: bool = Field(True, description="Enable colored logs")
    timeout: int = Field(30, description="Request timeout in seconds", ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)
    exts: List[str] = Field(default_factory=lambda: [".mp4", ".mkv", ".avi", ".mov"], description="Video extensions")
    alt_exts: List[str] = Field(default_factory=lambda: [".srt", ".ass"], description="Subtitle extensions")
    create_sub_directory: bool = Field(False, description="Create subdirectories globally")
    api_keys: Optional[APIKeysConfig] = Field(None, description="API瀵嗛挜閰嶇疆")
    telegram: TelegramConfig = Field(default_factory=TelegramConfig, description="Telegram閫氱煡閰嶇疆")
    wechat: WeChatConfig = Field(default_factory=WeChatConfig, description="寰俊閫氱煡閰嶇疆")
    webdav: WebDAVConfig = Field(default_factory=WebDAVConfig, description="WebDAV閰嶇疆")
    alist: AListConfig = Field(default_factory=AListConfig, description="AList閰嶇疆")
    
    # 鏂板瀛楁
    quark: QuarkConfig = Field(default_factory=QuarkConfig, description="澶稿厠缃戠洏閰嶇疆")
    tmdb: TmdbConfig = Field(default_factory=TmdbConfig, description="TMDB閰嶇疆")
    emby: GlobalEmbyConfig = Field(default_factory=GlobalEmbyConfig, description="Emby閰嶇疆")
    zhipu: ZhipuConfig = Field(default_factory=ZhipuConfig, description="鏅鸿氨AI閰嶇疆")
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig, description="DeepSeek AI configuration")
    glm: GLMConfig = Field(default_factory=GLMConfig, description="GLM AI configuration")
    kimi: KimiConfig = Field(default_factory=KimiConfig, description="Kimi AI configuration")
    cors: CorsConfig = Field(default_factory=CorsConfig, description="CORS settings")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Security settings")

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data):
        if isinstance(data, dict) and "ai" in data and "zhipu" not in data:
            data["zhipu"] = data.pop("ai")
        return data

    @field_validator('api_keys', mode='before')
    @classmethod
    def normalize_api_keys(cls, v):
        return v or {}

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
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
    def from_yaml(cls, path: str) -> 'AppConfig':
        """
        浠嶻AML鏂囦欢鍔犺浇閰嶇疆

        Args:
            path: YAML鏂囦欢璺緞

        Returns:
            AppConfig瀹炰緥
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        data = cls._apply_env_overrides(data)
        return cls(**data)

    @classmethod
    def _apply_env_overrides(cls, data: dict) -> dict:
        """Apply environment overrides for sensitive config values."""
        def _set_nested(target: dict, keys: list[str], value: str):
            current = target
            for key in keys[:-1]:
                if key not in current or not isinstance(current[key], dict):
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = value

        env_map = {
            "SMART_MEDIA_TMDB_API_KEY": ["tmdb", "api_key"],
            "SMART_MEDIA_ZHIPU_API_KEY": ["zhipu", "api_key"],
            "SMART_MEDIA_DEEPSEEK_API_KEY": ["deepseek", "api_key"],
            "SMART_MEDIA_GLM_API_KEY": ["glm", "api_key"],
            "SMART_MEDIA_KIMI_API_KEY": ["kimi", "api_key"],
            "SMART_MEDIA_TELEGRAM_BOT_TOKEN": ["telegram", "bot_token"],
            "SMART_MEDIA_TELEGRAM_CHAT_ID": ["telegram", "chat_id"],
            "SMART_MEDIA_QUARK_COOKIE": ["quark", "cookie"],
            "SMART_MEDIA_EMBY_URL": ["emby", "url"],
            "SMART_MEDIA_EMBY_API_KEY": ["emby", "api_key"],
            "SMART_MEDIA_WEBDAV_USERNAME": ["webdav", "username"],
            "SMART_MEDIA_WEBDAV_PASSWORD": ["webdav", "password"],
        }

        for env_key, path_keys in env_map.items():
            env_value = os.getenv(env_key)
            if env_value:
                _set_nested(data, path_keys, env_value)

        # Replace env var placeholders
        data = cls._replace_env_placeholders(data)
        return data

    @classmethod
    def _replace_env_placeholders(cls, data: any) -> any:
        """Replace ${VAR_NAME} or ${VAR_NAME:-default} placeholders recursively."""
        if isinstance(data, dict):
            return {key: cls._replace_env_placeholders(value) for key, value in data.items()}
        if isinstance(data, list):
            return [cls._replace_env_placeholders(item) for item in data]
        if isinstance(data, str):
            import re
            # Match ${VAR_NAME} or ${VAR_NAME:-default} placeholders
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, data)

            for match in matches:
                if ':-' in match:
                    var_name, default_val = match.split(':-', 1)
                else:
                    var_name = match
                    default_val = ''

                env_value = os.getenv(var_name.strip())
                if env_value is not None:
                    data = data.replace(f'${{{match}}}', env_value)
                elif ':-' in match:  # Use default value
                    data = data.replace(f'${{{match}}}', default_val)
                # If env var not found and no default, keep original
            return data
        return data

    def to_yaml(self, path: str) -> None:
        """
        淇濆瓨閰嶇疆鍒癥AML鏂囦欢

        Args:
            path: YAML鏂囦欢璺緞
        """
        dirname = os.path.dirname(path)
        if dirname:  # Only create directory if path has a parent directory
            os.makedirs(dirname, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, allow_unicode=True, default_flow_style=False)

