"""
通知服务基类模块

定义通知服务的抽象基类和通用数据模型。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class NotificationPriority(str, Enum):
    """通知优先级枚举"""

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class NotificationMessage:
    """
    通知消息数据类

    Attributes:
        title: 通知标题
        content: 通知内容
        priority: 通知优先级
        metadata: 附加元数据
        timestamp: 消息创建时间
    """

    title: str
    content: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class BaseNotifier(ABC):
    """
    通知器抽象基类

    所有具体通知渠道（Telegram、微信等）都需要继承此类并实现send方法。

    Example:
        class MyNotifier(BaseNotifier):
            async def send(self, message: NotificationMessage) -> bool:
                # 实现发送逻辑
                return True

            @property
            def name(self) -> str:
                return "my_notifier"
    """

    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        """
        发送通知消息

        Args:
            message: 要发送的通知消息对象

        Returns:
            bool: 发送是否成功
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        获取通知器名称

        Returns:
            str: 通知器标识名称
        """

    async def is_healthy(self) -> bool:
        """
        检查通知服务健康状态

        Returns:
            bool: 服务是否健康，默认返回True
        """
        return True

    def validate_config(self) -> bool:
        """
        验证通知器配置是否有效

        Returns:
            bool: 配置是否有效，默认返回True
        """
        return True
