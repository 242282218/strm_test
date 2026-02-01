"""
配置管理模块

参考: AlistAutoStrm config.go
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import yaml
import os


class EndpointConfig(BaseModel):
    """端点配置"""
    base_url: str = Field(..., description="OpenList/AList base URL")
    token: Optional[str] = Field(None, description="API token")
    username: Optional[str] = Field(None, description="Username")
    password: Optional[str] = Field(None, description="Password")
    insecure_tls_verify: bool = Field(False, description="Skip TLS verification")
    dirs: List['DirConfig'] = Field(default_factory=list, description="Directory mappings")
    max_connections: int = Field(5, description="Max concurrent connections")
    emby_url: Optional[str] = Field(None, description="Emby server URL")
    emby_api_key: Optional[str] = Field(None, description="Emby API key")

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if not v:
            raise ValueError('base_url cannot be empty')
        return v.rstrip('/')


class DirConfig(BaseModel):
    """目录配置"""
    local_directory: str = Field(..., description="Local directory path")
    remote_directories: List[str] = Field(..., description="Remote directory paths")
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
    ai_api_key: Optional[str] = Field(None, description="AI API密钥")
    tmdb_api_key: Optional[str] = Field(None, description="TMDB API密钥")


class AppConfig(BaseModel):
    """应用配置"""
    database: str = Field("quark_strm.db", description="Database file path")
    endpoints: List[EndpointConfig] = Field(default_factory=list, description="Endpoint configurations")
    log_level: str = Field("INFO", description="Log level")
    log_file: Optional[str] = Field(None, description="Log file path")
    colored_log: bool = Field(True, description="Enable colored logs")
    timeout: int = Field(30, description="Request timeout in seconds")
    exts: List[str] = Field(default_factory=lambda: [".mp4", ".mkv", ".avi", ".mov"], description="Video extensions")
    alt_exts: List[str] = Field(default_factory=lambda: [".srt", ".ass"], description="Subtitle extensions")
    create_sub_directory: bool = Field(False, description="Create subdirectories globally")
    api_keys: Optional[APIKeysConfig] = Field(None, description="API密钥配置")

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()

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
            data = yaml.safe_load(f)

        return cls(**data)

    def to_yaml(self, path: str) -> None:
        """
        保存配置到YAML文件

        Args:
            path: YAML文件路径
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, allow_unicode=True, default_flow_style=False)
