from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from app.services.config_service import get_config_service, ConfigError
from app.core.logging import get_logger
from app.core.dependencies import require_api_key
from app.core.security import mask_secret
from app.core.constants import SENSITIVE_FIELD_NAMES
import os
import aiohttp
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.core.validators import validate_http_url

logger = get_logger(__name__)
router = APIRouter(prefix="/api/system-config", tags=["系统配置"])

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(name in key_lower for name in SENSITIVE_FIELD_NAMES)


def _is_masked_placeholder(value: object) -> bool:
    return isinstance(value, str) and "*" in value


def _merge_sensitive_values(current: object, incoming: object, key_name: str = "") -> object:
    """
    Merge incoming config with current config.
    For sensitive fields, masked placeholders keep existing values.
    """
    if isinstance(incoming, dict) and isinstance(current, dict):
        merged: dict[str, object] = {}
        for key, value in incoming.items():
            current_value = current.get(key)
            if _is_sensitive_key(key) and _is_masked_placeholder(value):
                merged[key] = current_value
                continue
            merged[key] = _merge_sensitive_values(current_value, value, key)
        return merged

    if isinstance(incoming, list) and isinstance(current, list):
        result: list[object] = []
        for index, value in enumerate(incoming):
            current_value = current[index] if index < len(current) else None
            result.append(_merge_sensitive_values(current_value, value, key_name))
        return result

    if _is_sensitive_key(key_name) and _is_masked_placeholder(incoming):
        return current
    return incoming


def get_config_path():
    """
    获取配置文件路径

    Args:
        无

    Returns:
        str: 配置文件路径
    """
    return CONFIG_PATH


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
        raise HTTPException(status_code=500, detail=str(e))


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
        merged_payload = _merge_sensitive_values(current_config, config_data)
        config = config_service.update_config(merged_payload)
        logger.info("System configuration updated")
        return config_service.get_safe_config()
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SingleAIModelConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field("", max_length=2048)
    base_url: str = Field(..., min_length=1, max_length=2048)
    model: str = Field(..., min_length=1, max_length=256)
    timeout: int = Field(..., ge=1, le=120)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v):
        value = v.strip().rstrip("/")
        validate_http_url(value, "base_url")
        return value

    @field_validator("model")
    @classmethod
    def validate_model(cls, v):
        value = v.strip()
        if not value:
            raise ValueError("model cannot be empty")
        return value


class AIModelsConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kimi: SingleAIModelConfigUpdate
    deepseek: SingleAIModelConfigUpdate
    glm: SingleAIModelConfigUpdate


def _build_ai_models_response(config) -> dict:
    glm_key = (
        (config.glm.api_key if getattr(config, "glm", None) else "")
        or (config.zhipu.api_key if getattr(config, "zhipu", None) else "")
        or (config.api_keys.ai_api_key if config.api_keys else "")
        or ""
    )
    deepseek_key = config.deepseek.api_key if getattr(config, "deepseek", None) else ""
    kimi_key = config.kimi.api_key if getattr(config, "kimi", None) else ""

    return {
        "kimi": {
            "configured": bool(kimi_key),
            "api_key_masked": mask_secret(kimi_key),
            "base_url": config.kimi.base_url,
            "model": config.kimi.model,
            "timeout": config.kimi.timeout,
        },
        "deepseek": {
            "configured": bool(deepseek_key),
            "api_key_masked": mask_secret(deepseek_key),
            "base_url": config.deepseek.base_url,
            "model": config.deepseek.model,
            "timeout": config.deepseek.timeout,
        },
        "glm": {
            "configured": bool(glm_key),
            "api_key_masked": mask_secret(glm_key),
            "base_url": config.glm.base_url,
            "model": config.glm.model,
            "timeout": config.glm.timeout,
        },
    }


def _resolve_api_key_update(new_value: str, current_value: str) -> str:
    value = (new_value or "").strip()
    if not value:
        return current_value
    if "*" in value:
        return current_value
    return value


class QuarkConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cookie: str = Field("", max_length=8192)
    referer: str = Field("https://pan.quark.cn/", min_length=1, max_length=2048)
    root_id: str = Field("0", min_length=1, max_length=64)
    only_video: bool = Field(True)

    @field_validator("referer")
    @classmethod
    def validate_referer(cls, v: str) -> str:
        value = v.strip()
        validate_http_url(value, "quark.referer")
        return value

    @field_validator("root_id")
    @classmethod
    def validate_root_id(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("root_id cannot be empty")
        return value


def _build_quark_response(config) -> dict:
    quark = getattr(config, "quark", None)
    cookie = quark.cookie if quark else ""
    return {
        "configured": bool(cookie),
        "cookie_masked": mask_secret(cookie, prefix_len=6, suffix_len=6),
        "referer": quark.referer if quark else "https://pan.quark.cn/",
        "root_id": quark.root_id if quark else "0",
        "only_video": bool(quark.only_video) if quark else True,
    }


@router.get("/quark")
async def get_quark_config(_auth: None = Depends(require_api_key)):
    """Get Quark config with masked cookie."""
    try:
        config_service = get_config_service(CONFIG_PATH)
        config = config_service.get_config()
        return _build_quark_response(config)
    except Exception as e:
        logger.error(f"Failed to read Quark config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quark")
async def update_quark_config(
    payload: QuarkConfigUpdateRequest,
    _auth: None = Depends(require_api_key),
):
    """Update Quark config safely (blank/masked cookie keeps current value)."""
    try:
        config_service = get_config_service(CONFIG_PATH)
        current = config_service.get_config()
        config_dict = current.model_dump()

        current_cookie = config_dict.get("quark", {}).get("cookie", "")
        incoming_cookie = (payload.cookie or "").strip()
        if not incoming_cookie or "*" in incoming_cookie:
            resolved_cookie = current_cookie
        else:
            resolved_cookie = incoming_cookie

        config_dict["quark"]["cookie"] = resolved_cookie
        config_dict["quark"]["referer"] = payload.referer
        config_dict["quark"]["root_id"] = payload.root_id
        config_dict["quark"]["only_video"] = payload.only_video

        updated = config_service.update_config(config_dict)
        logger.info("Quark configuration updated")
        return _build_quark_response(updated)
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update Quark config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-models")
async def get_ai_models_config(_auth: None = Depends(require_api_key)):
    """Get current AI model config with masked sensitive values."""
    try:
        config_service = get_config_service(CONFIG_PATH)
        config = config_service.get_config()
        return _build_ai_models_response(config)
    except Exception as e:
        logger.error(f"Failed to read AI model config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-models")
async def update_ai_models_config(
    payload: AIModelsConfigUpdateRequest,
    _auth: None = Depends(require_api_key),
):
    """Update AI model config safely (blank/masked api_key keeps current value)."""
    try:
        config_service = get_config_service(CONFIG_PATH)
        current = config_service.get_config()
        config_dict = current.model_dump()

        for provider in ("kimi", "deepseek", "glm"):
            incoming = getattr(payload, provider)
            current_key = config_dict.get(provider, {}).get("api_key", "")
            config_dict[provider]["api_key"] = _resolve_api_key_update(incoming.api_key, current_key)
            config_dict[provider]["base_url"] = incoming.base_url
            config_dict[provider]["model"] = incoming.model
            config_dict[provider]["timeout"] = incoming.timeout

        updated = config_service.update_config(config_dict)
        logger.info("AI model configuration updated")
        return _build_ai_models_response(updated)
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update AI model config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        "parse_mode": "HTML"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, proxy=proxy if proxy else None) as resp:
                result = await resp.json()
                if result.get("ok"):
                    return {"success": True, "message": "测试消息发送成功"}
                else:
                    return {"success": False, "message": result.get("description", "未知错误")}
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")
        return {"success": False, "message": str(e)}
