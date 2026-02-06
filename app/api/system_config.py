from fastapi import APIRouter, HTTPException, Depends
from app.services.config_service import get_config_service, ConfigError
from app.core.logging import get_logger
from app.core.dependencies import require_api_key
import os
import aiohttp
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.core.validators import validate_http_url

logger = get_logger(__name__)
router = APIRouter(prefix="/api/system-config", tags=["系统配置"])

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")


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
        config = config_service.update_config(config_data)
        logger.info("System configuration updated")
        return config_service.get_safe_config()
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
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
