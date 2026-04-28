"""
Telegram通知模块

通过Telegram Bot API发送通知消息。
"""

import aiohttp

from app.core.logging import get_logger

from .base import BaseNotifier, NotificationMessage, NotificationPriority


logger = get_logger(__name__)


class TelegramNotifier(BaseNotifier):
    """
    Telegram Bot通知器

    使用Telegram Bot API发送消息到指定聊天。
    支持代理配置以应对网络限制。

    Attributes:
        token: Telegram Bot Token
        chat_id: 目标聊天ID
        proxy_url: 可选的代理URL

    Example:
        notifier = TelegramNotifier(
            token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789",
            proxy_url="http://127.0.0.1:7890"
        )
        await notifier.send(NotificationMessage(
            title="测试标题",
            content="测试内容"
        ))
    """

    def __init__(self, token: str, chat_id: str, proxy_url: str | None = None):
        """
        初始化Telegram通知器

        Args:
            token: Telegram Bot Token
            chat_id: 目标聊天ID（可以是用户ID或频道ID）
            proxy_url: 可选的HTTP代理URL
        """
        self.token = token
        self.chat_id = chat_id
        self.proxy_url = proxy_url
        self._api_base = f"https://api.telegram.org/bot{token}"

    @property
    def name(self) -> str:
        """获取通知器名称"""
        return "telegram"

    def validate_config(self) -> bool:
        """
        验证配置是否有效

        Returns:
            bool: token和chat_id是否都已配置
        """
        return bool(self.token and self.chat_id)

    async def send(self, message: NotificationMessage) -> bool:
        """
        发送Telegram消息

        使用Markdown格式发送标题和内容。
        低优先级消息会静默发送（无通知声音）。

        Args:
            message: 要发送的通知消息

        Returns:
            bool: 发送是否成功
        """
        if not self.validate_config():
            logger.error("Telegram notifier config invalid: token or chat_id missing")
            return False

        url = f"{self._api_base}/sendMessage"

        # 构建消息文本（Markdown格式）
        text = f"*{self._escape_markdown(message.title)}*\n\n{message.content}"

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_notification": message.priority == NotificationPriority.LOW,
        }

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(url, json=payload, proxy=self.proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as resp,
            ):
                if resp.status == 200:
                    logger.info(f"Telegram notification sent: {message.title}")
                    return True
                error_text = await resp.text()
                logger.error(f"Telegram API error: {resp.status} - {error_text}")
                return False
        except aiohttp.ClientError as e:
            logger.error(f"Telegram request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram notification: {e}")
            return False

    async def is_healthy(self) -> bool:
        """
        检查Bot是否可用

        通过调用getMe接口验证token有效性。

        Returns:
            bool: Bot API是否可访问
        """
        if not self.validate_config():
            return False

        url = f"{self._api_base}/getMe"

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, proxy=self.proxy_url, timeout=aiohttp.ClientTimeout(total=10)) as resp,
            ):
                return resp.status == 200
        except Exception as e:
            logger.debug(f"Telegram health check failed: {e}")
            return False

    def _escape_markdown(self, text: str) -> str:
        """
        转义Markdown特殊字符

        Telegram MarkdownV1需要转义以下字符：
        _ * [ ] ( ) ~ ` > # + - = | { } . !

        Args:
            text: 原始文本

        Returns:
            str: 转义后的文本
        """
        chars_to_escape = r"_*[]()~`>#+-=|{}.!"
        for char in chars_to_escape:
            text = text.replace(char, f"\\{char}")
        return text
