"""
微信通知模块

支持Server酱和的企业微信Webhook通知。
"""

import aiohttp

from app.core.logging import get_logger

from .base import BaseNotifier, NotificationMessage


logger = get_logger(__name__)


class ServerChanNotifier(BaseNotifier):
    """
    Server酱微信推送通知器

    通过Server酱API发送消息到微信。
    官网: https://sct.ftqq.com/

    Attributes:
        send_key: Server酱SendKey

    Example:
        notifier = ServerChanNotifier(send_key="SCT1234567890abcdef")
        await notifier.send(NotificationMessage(
            title="测试标题",
            content="测试内容"
        ))
    """

    def __init__(self, send_key: str):
        """
        初始化Server酱通知器

        Args:
            send_key: Server酱SendKey
        """
        self.send_key = send_key
        self._api_url = f"https://sctapi.ftqq.com/{send_key}.send"

    @property
    def name(self) -> str:
        """获取通知器名称"""
        return "serverchan"

    def validate_config(self) -> bool:
        """
        验证配置是否有效

        Returns:
            bool: send_key是否已配置
        """
        return bool(self.send_key)

    async def send(self, message: NotificationMessage) -> bool:
        """
        发送Server酱消息

        Args:
            message: 要发送的通知消息

        Returns:
            bool: 发送是否成功
        """
        if not self.validate_config():
            logger.error("ServerChan config invalid: send_key missing")
            return False

        payload = {"title": message.title, "desp": message.content}

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(self._api_url, data=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp,
            ):
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("code") == 0:
                        logger.info(f"ServerChan notification sent: {message.title}")
                        return True
                    logger.error(f"ServerChan API error: {result}")
                    return False
                error_text = await resp.text()
                logger.error(f"ServerChan HTTP error: {resp.status} - {error_text}")
                return False
        except aiohttp.ClientError as e:
            logger.error(f"ServerChan request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending ServerChan notification: {e}")
            return False


class WeChatWorkNotifier(BaseNotifier):
    """
    企业微信机器人通知器

    通过企业微信群机器人Webhook发送消息。
    文档: https://developer.work.weixin.qq.com/document/path/91770

    Attributes:
        webhook_url: 企业微信机器人Webhook地址

    Example:
        notifier = WeChatWorkNotifier(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )
        await notifier.send(NotificationMessage(
            title="测试标题",
            content="测试内容"
        ))
    """

    def __init__(self, webhook_url: str):
        """
        初始化企业微信通知器

        Args:
            webhook_url: 企业微信机器人Webhook地址
        """
        self.webhook_url = webhook_url

    @property
    def name(self) -> str:
        """获取通知器名称"""
        return "wechat_work"

    def validate_config(self) -> bool:
        """
        验证配置是否有效

        Returns:
            bool: webhook_url是否已配置
        """
        return bool(self.webhook_url and self.webhook_url.startswith("https://"))

    async def send(self, message: NotificationMessage) -> bool:
        """
        发送企业微信消息

        使用markdown格式发送消息。

        Args:
            message: 要发送的通知消息

        Returns:
            bool: 发送是否成功
        """
        if not self.validate_config():
            logger.error("WeChatWork config invalid: webhook_url missing or invalid")
            return False

        payload = {"msgtype": "markdown", "markdown": {"content": f"**{message.title}**\n\n{message.content}"}}

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp,
            ):
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("errcode") == 0:
                        logger.info(f"WeChatWork notification sent: {message.title}")
                        return True
                    logger.error(f"WeChatWork API error: {result}")
                    return False
                error_text = await resp.text()
                logger.error(f"WeChatWork HTTP error: {resp.status} - {error_text}")
                return False
        except aiohttp.ClientError as e:
            logger.error(f"WeChatWork request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending WeChatWork notification: {e}")
            return False


# 别名，方便导入
WeChatNotifier = ServerChanNotifier
