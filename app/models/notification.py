from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class NotificationChannel(Base):
    """通知渠道配置表"""

    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_type = Column(String(50), nullable=False)  # telegram/bark/serverchan/webhook
    channel_name = Column(String(100), nullable=False)
    is_enabled = Column(Boolean, default=True)
    config = Column(JSON, nullable=False)  # 渠道特定配置
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())

    # 关系
    rules = relationship("NotificationRule", back_populates="channel", cascade="all, delete-orphan")


class NotificationRule(Base):
    """通知规则表"""

    __tablename__ = "notification_rules"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("notification_channels.id"))
    event_type = Column(String(50), nullable=False)  # sync_finish/scrape_finish/media_added/...
    keywords = Column(String(200), nullable=True)  # 关键词过滤(可选)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # 关系
    channel = relationship("NotificationChannel", back_populates="rules")


class NotificationLog(Base):
    """通知发送日志表"""

    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("notification_channels.id"))
    channel_name = Column(String(100))  # 冗余存储，防止渠道删除后查不到
    event_type = Column(String(50), nullable=False)
    title = Column(String(200))
    content = Column(Text)
    status = Column(String(20))  # success/failed
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
