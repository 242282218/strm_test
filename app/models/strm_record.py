"""
STRM 记录 ORM 模型

统一数据库层，替代原生 SQLite3 操作
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.logging import get_logger


logger = get_logger(__name__)


class StrmRecord(Base):
    """
    STRM 记录模型

    对应原 database.py 中的 strm 表
    """

    __tablename__ = "strm_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(64), unique=True, nullable=False, index=True, comment="文件唯一标识(SHA1哈希)")
    file_name = Column(String(512), nullable=False, comment="STRM文件名")
    strm_path = Column(String(1024), nullable=True, comment="STRM文件本地路径")
    local_dir = Column(String(1024), nullable=False, comment="本地目录")
    remote_dir = Column(String(1024), nullable=False, index=True, comment="远程目录")
    raw_url = Column(String(2048), nullable=False, comment="原始URL")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")

    # 添加复合索引优化查询
    __table_args__ = (
        Index("idx_strm_records_remote_dir", "remote_dir"),
        Index("idx_strm_records_file_id", "file_id"),
    )

    @classmethod
    def create_or_update(
        cls,
        db: Session,
        file_id: str,
        file_name: str,
        local_dir: str,
        remote_dir: str,
        raw_url: str,
        strm_path: str | None = None,
    ) -> "StrmRecord":
        """
        创建或更新 STRM 记录

        Args:
            db: 数据库会话
            file_id: 文件唯一标识
            file_name: STRM文件名
            local_dir: 本地目录
            remote_dir: 远程目录
            raw_url: 原始URL
            strm_path: STRM文件路径

        Returns:
            StrmRecord 实例
        """
        record = db.query(cls).filter(cls.file_id == file_id).first()

        if record:
            record.file_name = file_name
            record.local_dir = local_dir
            record.remote_dir = remote_dir
            record.raw_url = raw_url
            record.updated_at = datetime.utcnow()
            if strm_path:
                record.strm_path = strm_path
            logger.debug(f"Updated STRM record: {file_id}")
        else:
            record = cls(
                file_id=file_id,
                file_name=file_name,
                local_dir=local_dir,
                remote_dir=remote_dir,
                raw_url=raw_url,
                strm_path=strm_path,
            )
            db.add(record)
            logger.debug(f"Created STRM record: {file_id}")

        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def get_by_file_id(cls, db: Session, file_id: str) -> Optional["StrmRecord"]:
        """
        根据 file_id 获取记录

        Args:
            db: 数据库会话
            file_id: 文件唯一标识

        Returns:
            StrmRecord 实例或 None
        """
        return db.query(cls).filter(cls.file_id == file_id).first()

    @classmethod
    def get_by_remote_dir(cls, db: Session, remote_dir: str) -> list["StrmRecord"]:
        """
        根据远程目录获取记录列表

        Args:
            db: 数据库会话
            remote_dir: 远程目录路径

        Returns:
            StrmRecord 列表
        """
        return db.query(cls).filter(cls.remote_dir == remote_dir).all()

    @classmethod
    def get_all(cls, db: Session) -> list["StrmRecord"]:
        """
        获取所有记录

        Args:
            db: 数据库会话

        Returns:
            StrmRecord 列表
        """
        return db.query(cls).all()

    @classmethod
    def delete_by_file_id(cls, db: Session, file_id: str) -> bool:
        """
        根据 file_id 删除记录

        Args:
            db: 数据库会话
            file_id: 文件唯一标识

        Returns:
            是否删除成功
        """
        try:
            count = db.query(cls).filter(cls.file_id == file_id).delete()
            db.commit()
            if count > 0:
                logger.debug(f"Deleted STRM record: {file_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete STRM record {file_id}: {e}")
            return False

    @classmethod
    def delete_by_remote_dir(cls, db: Session, remote_dir: str) -> int:
        """
        根据远程目录删除所有记录

        Args:
            db: 数据库会话
            remote_dir: 远程目录路径

        Returns:
            删除的记录数
        """
        try:
            count = db.query(cls).filter(cls.remote_dir == remote_dir).delete()
            db.commit()
            logger.info(f"Deleted {count} STRM records from {remote_dir}")
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete STRM records by remote dir {remote_dir}: {e}")
            return 0

    def to_dict(self) -> dict:
        """
        转换为字典格式（兼容原 database.py 返回格式）

        Returns:
            字典格式的记录数据
        """
        return {
            "id": self.id,
            "key": self.file_id,  # 兼容旧字段名
            "file_id": self.file_id,
            "name": self.file_name,  # 兼容旧字段名
            "file_name": self.file_name,
            "strm_path": self.strm_path,
            "local_dir": self.local_dir,
            "remote_dir": self.remote_dir,
            "raw_url": self.raw_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<StrmRecord(file_id={self.file_id!r}, file_name={self.file_name!r})>"


class ScanRecord(Base):
    """
    扫描记录模型

    对应原 database.py 中的 records 表
    """

    __tablename__ = "scan_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    remote_dir = Column(String(1024), unique=True, nullable=False, comment="远程目录路径")
    last_scan = Column(DateTime, default=datetime.utcnow, nullable=False, comment="最后扫描时间")

    @classmethod
    def create_or_update(cls, db: Session, remote_dir: str) -> "ScanRecord":
        """
        创建或更新扫描记录

        Args:
            db: 数据库会话
            remote_dir: 远程目录路径

        Returns:
            ScanRecord 实例
        """
        record = db.query(cls).filter(cls.remote_dir == remote_dir).first()

        if record:
            record.last_scan = datetime.utcnow()
        else:
            record = cls(remote_dir=remote_dir)
            db.add(record)

        db.commit()
        db.refresh(record)
        logger.debug(f"Saved scan record: {remote_dir}")
        return record

    @classmethod
    def get_all(cls, db: Session) -> dict:
        """
        获取所有扫描记录

        Args:
            db: 数据库会话

        Returns:
            {remote_dir: last_scan} 字典
        """
        records = db.query(cls).all()
        return {r.remote_dir: r.last_scan for r in records}

    @classmethod
    def delete_by_remote_dir(cls, db: Session, remote_dir: str) -> bool:
        """
        删除扫描记录

        Args:
            db: 数据库会话
            remote_dir: 远程目录路径

        Returns:
            是否删除成功
        """
        try:
            count = db.query(cls).filter(cls.remote_dir == remote_dir).delete()
            db.commit()
            return count > 0
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete scan record {remote_dir}: {e}")
            return False

    def __repr__(self) -> str:
        return f"<ScanRecord(remote_dir={self.remote_dir!r}, last_scan={self.last_scan!r})>"
