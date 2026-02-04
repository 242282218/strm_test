"""
配置管理模块

参考: AlistAutoStrm config.go
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import List, Optional
import yaml
import os
from app.core.validators import validate_http_url
from app.core.constants import MAX_URL_LENGTH, MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS
from app.core.encryption import get_decrypted_config_value


class EndpointConfig(BaseModel):
    """端点配置"""
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
    """目录配置"""
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
    """API密钥配置"""
    model_config = ConfigDict(extra="forbid")

    ai_api_key: Optional[str] = Field(None, description="AI API密钥", max_length=2048)
    tmdb_api_key: Optional[str] = Field(None, description="TMDB API密钥", max_length=2048)


class TelegramConfig(BaseModel):
    """Telegram通知配置"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用Telegram通知")
    bot_token: str = Field("", description="Telegram Bot Token", max_length=2048)
    chat_id: str = Field("", description="接收消息的Chat ID", max_length=256)
    proxy: str = Field("", description="代理服务器地址", max_length=MAX_URL_LENGTH)
    events: List[str] = Field(
        default_factory=lambda: ["task_completed", "task_failed"],
        description="需要推送的事件类型"
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
        # 如果是环境变量占位符格式，则跳过验证
        if v and (v.startswith('${') and v.endswith('}')):
            return v
        if v:
            validate_http_url(v, "proxy")
        return v


class WeChatConfig(BaseModel):
    """微信通知配置"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用微信通知")
    provider: str = Field("serverchan", description="服务提供商", max_length=256)
    send_key: str = Field("", description="SendKey", max_length=2048)



class AListConfig(BaseModel):
    """AList配置"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用AList集成")
    url: str = Field("http://localhost:5244", description="AList服务地址", max_length=MAX_URL_LENGTH)
    token: str = Field("", description="AList Token", max_length=2048)
    mount_path: str = Field("/", description="夸克网盘在AList中的挂载路径")

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
    """WebDAV配置（用于兜底播放）"""
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="是否启用WebDAV兜底功能")
    fallback_enabled: bool = Field(True, description="是否启用故障自动切换")
    url: str = Field("http://localhost:5244/dav", description="WebDAV服务地址", max_length=MAX_URL_LENGTH)
    username: str = Field("", description="WebDAV用户名", max_length=128)
    password: str = Field("", description="WebDAV密码", max_length=256)
    mount_path: str = Field("/", description="夸克网盘在WebDAV中的挂载路径")
    read_only: bool = Field(True, description="是否只读（仅用于内置WebDAV服务，此处无用但保留兼容）")

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
    """夸克网盘配置"""
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
    """TMDB配置"""
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="TMDB API Key", max_length=2048)

    @field_validator('api_key')
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class GlobalEmbyConfig(BaseModel):
    """全局Emby配置"""
    model_config = ConfigDict(extra="forbid")

    url: str = Field("", description="Emby Server URL", max_length=MAX_URL_LENGTH)
    api_key: str = Field("", description="Emby API Key", max_length=2048)

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        # 如果是环境变量占位符格式，则跳过验证
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
    """智谱AI配置"""
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", description="Zhipu AI API Key", max_length=2048)

    @field_validator('api_key')
    @classmethod
    def validate_and_decrypt_api_key(cls, v):
        if v and v.startswith("encrypted:"):
            return get_decrypted_config_value(v)
        return v


class AppConfig(BaseModel):
    """应用配置"""
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
    api_keys: Optional[APIKeysConfig] = Field(None, description="API密钥配置")
    telegram: TelegramConfig = Field(default_factory=TelegramConfig, description="Telegram通知配置")
    wechat: WeChatConfig = Field(default_factory=WeChatConfig, description="微信通知配置")
    webdav: WebDAVConfig = Field(default_factory=WebDAVConfig, description="WebDAV配置")
    alist: AListConfig = Field(default_factory=AListConfig, description="AList配置")
    
    # 新增字段
    quark: QuarkConfig = Field(default_factory=QuarkConfig, description="夸克网盘配置")
    tmdb: TmdbConfig = Field(default_factory=TmdbConfig, description="TMDB配置")
    emby: GlobalEmbyConfig = Field(default_factory=GlobalEmbyConfig, description="Emby配置")
    zhipu: ZhipuConfig = Field(default_factory=ZhipuConfig, description="智谱AI配置")

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
        从YAML文件加载配置

        Args:
            path: YAML文件路径

        Returns:
            AppConfig实例
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        data = cls._apply_env_overrides(data)
        return cls(**data)

    @classmethod
    def _apply_env_overrides(cls, data: dict) -> dict:
        """从环境变量覆盖敏感配置"""
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
        
        # 替换配置数据中的环境变量占位符
        data = cls._replace_env_placeholders(data)
        return data

    @classmethod
    def _replace_env_placeholders(cls, data: any) -> any:
        """递归替换数据中的环境变量占位符 ${VAR_NAME} 或 ${VAR_NAME:-default}"""
        if isinstance(data, dict):
            return {key: cls._replace_env_placeholders(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [cls._replace_env_placeholders(item) for item in data]
        elif isinstance(data, str):
            import re
            # 匹配 ${VAR_NAME} 或 ${VAR_NAME:-default} 格式的占位符
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
                elif ':-' in match:  # 如果提供了默认值
                    data = data.replace(f'${{{match}}}', default_val)
                # 如果没有默认值且环境变量不存在，则保留原字符串
            return data
        else:
            return data

    def to_yaml(self, path: str) -> None:
        """
        保存配置到YAML文件

        Args:
            path: YAML文件路径
        """
        dirname = os.path.dirname(path)
        if dirname:  # Only create directory if path has a parent directory
            os.makedirs(dirname, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, allow_unicode=True, default_flow_style=False)
