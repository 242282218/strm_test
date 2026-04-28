from typing import TYPE_CHECKING, Optional, Protocol


# 定义ChannelHandler协议
class ChannelHandler(Protocol):
    async def send(self, message: "NotificationMessage") -> bool: ...
    def get_channel_type(self) -> str: ...
    async def is_healthy(self) -> bool: ...
    def validate_config(self) -> bool: ...


if TYPE_CHECKING:
    from app.services.notification import BaseNotifier
import asyncio
import logging
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.notification import NotificationChannel, NotificationLog, NotificationRule
from app.services.config_service import get_config_service
from app.services.notification import (
    BaseNotifier,
    NotificationMessage,
    NotificationPriority,
    TelegramNotifier,
    WeChatNotifier,
)


logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """通知类型"""

    SYNC_FINISHED = "sync_finish"
    SYNC_ERROR = "sync_error"
    SCRAPE_FINISHED = "scrape_finish"
    SCRAPE_ERROR = "scrape_error"
    SYSTEM_ALERT = "system_alert"
    MEDIA_ADDED = "media_added"
    MEDIA_REMOVED = "media_removed"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    # 安全事件类型
    SECURITY_LOGIN_FAILED = "security_login_failed"
    SECURITY_ACCOUNT_LOCKED = "security_account_locked"
    SECURITY_UNAUTHORIZED_ACCESS = "security_unauthorized_access"
    SECURITY_CONFIG_CHANGE = "security_config_change"
    SECURITY_INJECTION_ATTEMPT = "security_injection_attempt"
    SECURITY_ALERT = "security_alert"


class NotificationPriority(str, Enum):
    """通知优先级"""

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# ==================== 兼容层：旧版NotificationMessage ====================


class NotificationMessage:
    """
    通知消息（兼容层）

    用于NotificationService内部的消息传递，保持与现有代码兼容。
    """

    def __init__(
        self,
        type: NotificationType,
        title: str,
        content: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: dict | None = None,
    ):
        self.type = type
        self.title = title
        self.content = content
        self.priority = priority
        self.metadata = metadata or {}
        self.created_at = datetime.now()


# ==================== 适配器：将旧ChannelHandler接口适配到新BaseNotifier ====================


class ChannelHandlerAdapter:
    """
    渠道处理器适配器

    将新的BaseNotifier适配到NotificationService使用的内部接口
    """

    def __init__(self, notifier: BaseNotifier, channel_name: str):
        self.notifier = notifier
        self.channel_name = channel_name

    async def send(self, message: "NotificationMessage") -> bool:
        """发送通知"""
        # 将旧的NotificationMessage转换为新的NotificationMessage
        from app.services.notification import NotificationMessage as NewMessage

        new_message = NewMessage(title=message.title, content=message.content, priority=message.priority)
        return await self.notifier.send(new_message)

    def get_channel_type(self) -> str:
        """获取渠道类型"""
        return self.notifier.name

    async def is_healthy(self) -> bool:
        """检查渠道健康状态"""
        return await self.notifier.is_healthy()

    def validate_config(self) -> bool:
        """验证配置"""
        return self.notifier.validate_config()


# ==================== 具体渠道实现（使用新的通知模块） ====================


class TelegramHandler:
    """Telegram Bot通知适配器"""

    def __init__(self, bot_token: str, chat_id: str, proxy: str | None = None, proxy_url: str | None = None):
        self.notifier = TelegramNotifier(token=bot_token, chat_id=chat_id, proxy_url=proxy_url or proxy)

    async def send(self, message: NotificationMessage) -> bool:
        from app.services.notification import NotificationMessage as NewMessage

        new_message = NewMessage(title=message.title, content=message.content, priority=message.priority)
        return await self.notifier.send(new_message)

    def get_channel_type(self) -> str:
        return "telegram"

    async def is_healthy(self) -> bool:
        return await self.notifier.is_healthy()

    @classmethod
    def validate_config(cls, config: dict) -> bool:
        return bool(config.get("bot_token") and config.get("chat_id"))


class ServerChanHandler:
    """Server酱微信推送适配器"""

    def __init__(self, send_key: str):
        self.notifier = WeChatNotifier(send_key=send_key)

    async def send(self, message: NotificationMessage) -> bool:
        from app.services.notification import NotificationMessage as NewMessage

        new_message = NewMessage(title=message.title, content=message.content, priority=message.priority)
        return await self.notifier.send(new_message)

    def get_channel_type(self) -> str:
        return "serverchan"

    async def is_healthy(self) -> bool:
        return True

    @classmethod
    def validate_config(cls, config: dict) -> bool:
        return bool(config.get("send_key"))


# ==================== 通知管理器 ====================


class NotificationService:
    """通知服务管理器"""

    _handlers_cls: dict[str, type] = {
        "telegram": TelegramHandler,
        # "bark": BarkHandler,
        "serverchan": ServerChanHandler,
        # "webhook": WebhookHandler,
    }

    _instance = None

    def __init__(self):
        self.channels: dict[int, ChannelHandler] = {}
        self.rules: dict[str, list[NotificationRule]] = {}  # event_type -> rules
        self._initialized = False

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = NotificationService()
        return cls._instance

    async def reload(self):
        """重新加载配置"""
        self.channels.clear()
        self.rules.clear()
        self._initialized = False
        await self.initialize()

    async def initialize(self):
        """
        初始化，从数据库加载配置，同时从 config.yaml 读取 Telegram 基础配置

        Args:
            无

        Returns:
            无

        Side Effects:
            加载数据库中的渠道和规则，自动创建 Telegram 渠道（如果配置了）
        """
        if self._initialized:
            return

        db: Session = SessionLocal()
        try:
            # 加载启用的渠道
            channels = db.query(NotificationChannel).filter(NotificationChannel.is_enabled == True).all()
            for ch in channels:
                handler = self._create_handler(ch)
                if handler:
                    self.channels[ch.id] = (handler, ch.channel_name)

            # 从 config.yaml 读取 Telegram 配置，如果配置了且未在数据库中，则自动创建
            try:
                config_service = get_config_service()
                config = config_service.get_config()
                if config.telegram.enabled and config.telegram.bot_token and config.telegram.chat_id:
                    # 检查是否已存在 Telegram 渠道
                    telegram_exists = any(ch.channel_type == "telegram" for ch in channels)
                    if not telegram_exists:
                        # 自动创建 Telegram 渠道
                        telegram_channel = NotificationChannel(
                            channel_name="Telegram (自动创建)",
                            channel_type="telegram",
                            config={
                                "bot_token": config.telegram.bot_token,
                                "chat_id": config.telegram.chat_id,
                                "proxy": config.telegram.proxy,
                            },
                            is_enabled=True,
                        )
                        db.add(telegram_channel)
                        db.commit()
                        db.refresh(telegram_channel)

                        # 创建处理器
                        handler = self._create_handler(telegram_channel)
                        if handler:
                            self.channels[telegram_channel.id] = (handler, telegram_channel.channel_name)

                        # 为所有事件创建规则
                        for event_type in config.telegram.events:
                            # 检查规则是否已存在
                            existing_rule = (
                                db.query(NotificationRule)
                                .filter(
                                    NotificationRule.channel_id == telegram_channel.id,
                                    NotificationRule.event_type == event_type,
                                )
                                .first()
                            )
                            if not existing_rule:
                                rule = NotificationRule(
                                    channel_id=telegram_channel.id, event_type=event_type, is_enabled=True
                                )
                                db.add(rule)
                        db.commit()

                        logger.info(f"自动创建 Telegram 渠道和规则: {len(config.telegram.events)} 个事件")
            except Exception as e:
                logger.warning(f"从 config.yaml 读取 Telegram 配置失败: {e}")

            # 加载启用的规则
            rules = db.query(NotificationRule).filter(NotificationRule.is_enabled == True).all()
            for rule in rules:
                if rule.event_type not in self.rules:
                    self.rules[rule.event_type] = []
                self.rules[rule.event_type].append(rule)

            self._initialized = True
            logger.info(f"NotificationService initialized: {len(self.channels)} channels, {len(rules)} rules")
        except Exception as e:
            logger.error(f"NotificationService initialization failed: {e}")
        finally:
            db.close()

    def _create_handler(self, channel_config: NotificationChannel) -> Optional["ChannelHandler"]:
        """创建处理器实例"""
        handler_class = self._handlers_cls.get(channel_config.channel_type)
        if not handler_class:
            return None

        try:
            return handler_class(**channel_config.config)
        except Exception as e:
            logger.error(f"创建渠道处理程序失败 {channel_config.channel_name}: {e}")
            return None

    async def send_notification(
        self,
        type: NotificationType,
        title: str,
        content: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: dict | None = None,
    ):
        """发送通知"""
        if not self._initialized:
            await self.initialize()

        message = NotificationMessage(type, title, content, priority, metadata)

        # 获取匹配的规则
        matched_rules = self.rules.get(type, [])
        if not matched_rules:
            logger.debug(f"No rules found for event: {type}")
            return

        # 确定需要发送的渠道ID (去重)
        channel_ids = set()
        for rule in matched_rules:
            # 可以在这里添加更多过滤逻辑，如关键词过滤
            if rule.keywords:
                if rule.keywords not in title and rule.keywords not in content:
                    continue
            channel_ids.add(rule.channel_id)

        # 并发发送
        tasks = []
        for ch_id in channel_ids:
            if ch_id in self.channels:
                handler, ch_name = self.channels[ch_id]
                tasks.append(asyncio.create_task(self._send_and_log(ch_id, ch_name, handler, message)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_and_log(
        self, channel_id: int, channel_name: str, handler: ChannelHandler, message: NotificationMessage
    ):
        """发送并记录日志"""
        status = "failed"
        error_msg = None

        try:
            success = await asyncio.wait_for(handler.send(message), timeout=15)
            if success:
                status = "success"
            else:
                error_msg = "Handler returned False"
        except TimeoutError:
            error_msg = "Timeout"
        except Exception as e:
            error_msg = str(e)

        # 记录日志到数据库
        # 注意: 这里每次都创建新的Session，可能对并发略有影响，但在通知场景下可接受
        try:
            db = SessionLocal()
            log = NotificationLog(
                channel_id=channel_id,
                channel_name=channel_name,
                event_type=message.type,
                title=message.title,
                content=message.content,
                status=status,
                error_message=error_msg,
            )
            db.add(log)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Failed to save notification log: {e}")

    # ==================== 快捷方法 ====================

    async def notify_sync_finished(self, sync_name: str, result: dict):
        """同步完成通知"""
        await self.send_notification(
            type=NotificationType.SYNC_FINISHED,
            title=f"✅ 同步完成: {sync_name}",
            content=f"新增: {result.get('new', 0)}, 更新: {result.get('updated', 0)}",
            priority=NotificationPriority.NORMAL,
            metadata=result,
        )

    async def notify_sync_error(self, sync_name: str, error: str):
        """同步失败通知"""
        await self.send_notification(
            type=NotificationType.SYNC_ERROR,
            title=f"❌ 同步失败: {sync_name}",
            content=str(error),
            priority=NotificationPriority.HIGH,
        )

    async def notify_media_added(self, media_name: str, media_type: str):
        """媒体入库通知"""
        await self.send_notification(
            type=NotificationType.MEDIA_ADDED,
            title="🎬 新媒体入库",
            content=f"{media_type}: {media_name}",
            priority=NotificationPriority.LOW,
        )

    async def notify_media_removed(self, media_name: str):
        """媒体删除通知"""
        await self.send_notification(
            type=NotificationType.MEDIA_REMOVED,
            title="🗑️ 媒体移除",
            content=f"{media_name}",
            priority=NotificationPriority.LOW,
        )


def get_notification_service() -> NotificationService:
    """获取单例"""
    return NotificationService.get_instance()
