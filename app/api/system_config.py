import os
from copy import deepcopy
from typing import Any

import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config.settings import AppConfig
from app.core.constants import SENSITIVE_FIELD_NAMES
from app.core.dependencies import require_api_key
from app.core.logging import get_logger
from app.core.security import mask_secret
from app.core.validators import validate_http_url
from app.services.config_service import ConfigError, get_config_service


logger = get_logger(__name__)
router = APIRouter(prefix="/api/system-config", tags=["系统配置"])

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(name in key_lower for name in SENSITIVE_FIELD_NAMES)


def _is_masked_sensitive_value(new_value: Any, current_value: Any) -> bool:
    # Config safe payload may return non-string secrets as "***" (e.g. booleans).
    if new_value in ("***", ""):
        return True
    if not isinstance(new_value, str):
        return False
    if isinstance(current_value, str) and current_value:
        return new_value == mask_secret(current_value)
    return False


def _restore_masked_sensitive_values(incoming: Any, current: Any) -> Any:
    if isinstance(incoming, dict) and isinstance(current, dict):
        restored: dict[str, Any] = {}
        for key, incoming_value in incoming.items():
            current_value = current.get(key)
            if _is_sensitive_key(key) and _is_masked_sensitive_value(incoming_value, current_value):
                restored[key] = deepcopy(current_value)
                continue
            restored[key] = _restore_masked_sensitive_values(incoming_value, current_value)
        return restored

    if isinstance(incoming, list) and isinstance(current, list):
        return [
            _restore_masked_sensitive_values(value, current[index] if index < len(current) else None)
            for index, value in enumerate(incoming)
        ]

    return incoming


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
            continue
        merged[key] = value
    return merged


def _build_config_metadata(config_service) -> dict[str, Any]:
    config = config_service.get_config()
    sensitive_fields_status = config.get_sensitive_fields_status()
    return {
        "schema": AppConfig.public_model_json_schema(),
        "sensitive_fields": sorted(sensitive_fields_status.keys()),
        "sensitive_fields_status": sensitive_fields_status,
    }


@router.get("/metadata")
async def get_config_metadata(_auth: None = Depends(require_api_key)):
    try:
        config_service = get_config_service(CONFIG_PATH)
        return _build_config_metadata(config_service)
    except Exception as e:
        logger.error(f"Failed to read config metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to read config metadata")


@router.get("/")
async def get_config(_auth: None = Depends(require_api_key)):
    """
    获取完整系统配置

    Args:
        无

    Returns:
        dict: 配置字典

    Side Effects:
        从 ConfigService 读取配置
    """
    try:
        config_service = get_config_service(CONFIG_PATH)
        return config_service.get_safe_config()
    except Exception as e:
        logger.error(f"Failed to read config: {e}")
        raise HTTPException(status_code=500, detail="Failed to read config")


@router.post("/")
async def update_config(config_data: dict, _auth: None = Depends(require_api_key)):
    """
    更新系统配置

    Args:
        config_data: 配置数据字典

    Returns:
        dict: 更新后的配置字典

    Side Effects:
        通过 ConfigService 保存配置到文件
    """
    try:
        config_service = get_config_service(CONFIG_PATH)
        current_config = config_service.get_config().model_dump()
        restored_payload = _restore_masked_sensitive_values(config_data, current_config)
        merged_payload = _deep_merge_dict(current_config, restored_payload)
        config_service.update_config(merged_payload)
        logger.info("System configuration updated")
        return config_service.get_safe_config()
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail="Failed to save config")


def _resolve_api_key_update(new_value: str, current_value: str) -> str:
    value = (new_value or "").strip()
    if not value:
        return current_value
    if "*" in value:
        return current_value
    return value


def _map_ai_models_response_to_providers(models_response: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    provider_order = ("kimi", "deepseek", "glm")
    return {
        "providers": [
            {
                "name": name,
                "api_key_masked": models_response[name]["api_key_masked"],
                "configured": models_response[name]["configured"],
                "base_url": models_response[name]["base_url"],
                "model": models_response[name]["model"],
                "timeout": models_response[name]["timeout"],
                "enabled": True,
                "priority": 100 - index * 10,
            }
            for index, name in enumerate(provider_order)
        ]
    }


def _normalize_ai_section(config_dict: dict) -> dict:
    """Ensure `config_dict['ai']` is always a mutable dict."""
    ai_section = config_dict.get("ai")
    if not isinstance(ai_section, dict):
        ai_section = {}
        config_dict["ai"] = ai_section
    return ai_section


# 新格式 AI Providers API
class AIProviderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=64)
    api_key: str = Field("", max_length=2048)
    base_url: str = Field(..., min_length=1, max_length=2048)
    model: str = Field(..., min_length=1, max_length=256)
    timeout: int = Field(..., ge=1, le=120)
    enabled: bool = True
    priority: int = Field(100, ge=0, le=1000)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v):
        value = v.strip().rstrip("/")
        validate_http_url(value, "base_url")
        return value


class AIProvidersUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: list[AIProviderItem]


@router.get("/ai-providers")
async def get_ai_providers(_auth: None = Depends(require_api_key)):
    """获取 AI providers 配置（统一格式）"""
    try:
        config_service = get_config_service(CONFIG_PATH)
        config = config_service.get_config()
        providers = []

        if hasattr(config, "ai") and config.ai and hasattr(config.ai, "providers"):
            providers = [
                {
                    "name": p.name,
                    "api_key_masked": mask_secret(p.api_key),
                    "configured": bool(p.api_key),
                    "base_url": p.base_url,
                    "model": p.model,
                    "timeout": p.timeout,
                    "enabled": p.enabled,
                    "priority": p.priority,
                }
                for p in config.ai.providers
            ]

        return {"providers": providers}
    except Exception as e:
        logger.error(f"Failed to read AI providers: {e}")
        raise HTTPException(status_code=500, detail="Failed to read AI providers")


@router.post("/ai-providers")
async def update_ai_providers(
    payload: AIProvidersUpdateRequest,
    _auth: None = Depends(require_api_key),
):
    """更新 AI providers 配置（新格式）"""
    try:
        config_service = get_config_service(CONFIG_PATH)
        current = config_service.get_config()
        config_dict = current.model_dump()
        ai_section = _normalize_ai_section(config_dict)

        # 构建新的 providers 列表
        current_provider_list = ai_section.get("providers")
        if not isinstance(current_provider_list, list):
            current_provider_list = []
        current_providers = {
            p["name"]: p for p in current_provider_list if isinstance(p, dict) and isinstance(p.get("name"), str)
        }
        new_providers = []

        for incoming in payload.providers:
            current_p = current_providers.get(incoming.name, {})
            new_providers.append(
                {
                    "name": incoming.name,
                    "api_key": _resolve_api_key_update(incoming.api_key, current_p.get("api_key", "")),
                    "base_url": incoming.base_url,
                    "model": incoming.model,
                    "timeout": incoming.timeout,
                    "enabled": incoming.enabled,
                    "priority": incoming.priority,
                }
            )

        ai_section["providers"] = new_providers
        config_service.update_config(config_dict)
        logger.info(f"AI providers updated: {len(new_providers)} providers")

        return await get_ai_providers(_auth)
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update AI providers: {e}")
        raise HTTPException(status_code=500, detail="Failed to update AI providers")


class TelegramTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bot_token: str = Field(..., min_length=1, max_length=2048)
    chat_id: str = Field(..., min_length=1, max_length=256)
    proxy: str = Field("", max_length=2048)

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, v):
        if v:
            validate_http_url(v, "proxy")
        return v


@router.post("/test-telegram")
async def test_telegram(config: TelegramTestRequest, _auth: None = Depends(require_api_key)):
    """
    测试 Telegram 推送

    Args:
        config: Telegram 配置字典，包含 bot_token, chat_id, proxy

    Returns:
        dict: 测试结果

    Side Effects:
        向 Telegram API 发送测试消息
    """
    bot_token = config.bot_token
    chat_id = config.chat_id
    proxy = config.proxy

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "📢 Quark-STRM 测试消息\n\n这是一条测试消息，如果您的配置正确，说明 Telegram 推送已正常工作。",
        "parse_mode": "HTML",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, proxy=proxy if proxy else None) as resp:
                result = await resp.json()
                if result.get("ok"):
                    return {"success": True, "message": "测试消息发送成功"}
                return {"success": False, "message": result.get("description", "未知错误")}
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")
        return {"success": False, "message": str(e)}
