"""
统一 AI Provider 配置（OpenAI 兼容）

支持任意 OpenAI 兼容的 API 端点，包括：
- OpenAI
- DeepSeek
- GLM (智谱)
- Kimi
- 其他兼容 OpenAI API 的服务
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import MAX_TIMEOUT_SECONDS, MAX_URL_LENGTH, MIN_TIMEOUT_SECONDS
from app.core.encryption import get_decrypted_config_value
from app.core.validators import validate_http_url


class AIProviderConfig(BaseModel):
    """单个 AI Provider 配置"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Provider name", max_length=64)
    api_key: str = Field("", description="API Key", max_length=2048)
    base_url: str = Field(..., description="API base URL (OpenAI compatible)", max_length=MAX_URL_LENGTH)
    model: str = Field(..., description="Model name", max_length=256)
    timeout: int = Field(30, description="Timeout in seconds", ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)
    enabled: bool = Field(True, description="Enable this provider")
    priority: int = Field(0, description="Priority (higher = try first)")

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
            validate_http_url(v, "ai.provider.base_url")
            return v
        return v


class AIConfig(BaseModel):
    """统一 AI 配置"""

    model_config = ConfigDict(extra="forbid")

    providers: list[AIProviderConfig] = Field(default_factory=list, description="AI providers list")
    max_retries: int = Field(3, description="Max retry attempts per provider", ge=0, le=10)
    fallback_enabled: bool = Field(True, description="Enable fallback to next provider on failure")

    @model_validator(mode="after")
    def validate_providers(self):
        if not self.providers:
            # 提供默认配置
            self.providers = [
                AIProviderConfig(
                    name="deepseek",
                    api_key="",
                    base_url="https://api.deepseek.com/v1",
                    model="deepseek-chat",
                    timeout=20,
                    priority=100,
                )
            ]
        return self

    def get_enabled_providers(self) -> list[AIProviderConfig]:
        """获取已启用的 providers，按优先级排序"""
        enabled = [p for p in self.providers if p.enabled and p.api_key]
        return sorted(enabled, key=lambda p: p.priority, reverse=True)
