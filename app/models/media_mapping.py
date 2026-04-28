"""
稳定媒体映射模型

用于将稳定的 media_id 映射到当前可变的后端文件信息。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String

from app.core.db import Base


class MediaMapping(Base):
    """稳定媒体映射表。"""

    __tablename__ = "media_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_id = Column(String(64), unique=True, nullable=False, index=True, comment="稳定媒体 ID")
    backend_id = Column(String(64), nullable=False, default="quark", comment="后端类型/标识")
    provider_file_id = Column(String(255), nullable=True, index=True, comment="上游文件 ID")
    source_path = Column(String(2048), nullable=False, index=True, comment="远端路径")
    display_name = Column(String(512), nullable=False, comment="展示文件名")
    source_ext = Column(String(64), nullable=True, comment="原始扩展名")
    strm_path = Column(String(2048), nullable=True, comment="本地 STRM 路径")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")

    __table_args__ = (
        Index("idx_media_mapping_backend_provider", "backend_id", "provider_file_id"),
        Index("idx_media_mapping_backend_source_path", "backend_id", "source_path"),
    )

    def __repr__(self) -> str:
        return (
            f"<MediaMapping(media_id={self.media_id!r}, backend_id={self.backend_id!r}, "
            f"provider_file_id={self.provider_file_id!r}, source_path={self.source_path!r})>"
        )
