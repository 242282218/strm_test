from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.db import Base


class CloudDrive(Base):
    """网盘账号模型"""

    __tablename__ = "cloud_drives"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, comment="账号自定义名称")
    drive_type = Column(String, nullable=False, comment="网盘类型: quark, 115, alist")
    cookie = Column(Text, nullable=False, comment="网盘Cookie")
    status = Column(String, default="active", comment="状态: active, inactive, expired")
    last_check = Column(DateTime(timezone=True), nullable=True, comment="上次检查时间")
    remark = Column(String, nullable=True, comment="备注")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
