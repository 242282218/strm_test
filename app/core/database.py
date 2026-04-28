"""
数据库模块（兼容层）

提供与原 Database 类兼容的接口，内部使用 SQLAlchemy ORM 实现
推荐直接使用 app.models.strm_record 中的 ORM 模型

参考: AlistAutoStrm BoltDB操作 (strm.go:49-57)

重构说明:
    - 使用上下文管理器模式管理 session 生命周期
    - 自动处理事务提交和回滚
    - 消除连接泄漏风险
"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.db import get_db_session, resolve_db_path
from app.core.logging import get_logger
from app.models.strm_record import ScanRecord, StrmRecord


logger = get_logger(__name__)


class Database:
    """
    数据库管理类（兼容层）

    内部使用 SQLAlchemy ORM 实现
    推荐直接使用 StrmRecord 和 ScanRecord 模型

    重构改进:
        - 使用上下文管理器确保 session 正确关闭
        - 自动事务管理（成功提交，异常回滚）
        - 消除连接泄漏风险

    参考: AlistAutoStrm BoltDB操作
    """

    def __init__(self, db_path: str):
        """
        初始化数据库（兼容层）

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = resolve_db_path(db_path)
        logger.info(f"Database compatibility layer initialized: {db_path}")

    @contextmanager
    def _get_session(self) -> Generator[Session, None, None]:
        """
        获取数据库会话的上下文管理器

        确保会话在使用后正确关闭，异常时自动回滚

        Yields:
            Session: SQLAlchemy 会话对象
        """
        with get_db_session() as session:
            yield session

    def save_strm(self, key: str, name: str, local_dir: str, remote_dir: str, raw_url: str) -> bool:
        """
        保存STRM记录

        Args:
            key: STRM唯一键
            name: STRM文件名
            local_dir: 本地目录
            remote_dir: 远程目录
            raw_url: 原始URL

        Returns:
            是否成功
        """
        try:
            with self._get_session() as db:
                StrmRecord.create_or_update(
                    db=db,
                    file_id=key,
                    file_name=name,
                    local_dir=local_dir,
                    remote_dir=remote_dir,
                    raw_url=raw_url,
                )
            logger.debug(f"STRM saved: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to save STRM {key}: {e!s}")
            return False

    def get_strm(self, key: str) -> dict | None:
        """
        获取STRM记录

        Args:
            key: STRM唯一键

        Returns:
            STRM记录字典，不存在返回None
        """
        try:
            with self._get_session() as db:
                record = StrmRecord.get_by_file_id(db, key)
                if record:
                    return record.to_dict()
                return None
        except Exception as e:
            logger.error(f"Failed to get STRM {key}: {e!s}")
            return None

    def delete_strm(self, key: str) -> bool:
        """
        删除STRM记录

        Args:
            key: STRM唯一键

        Returns:
            是否成功
        """
        try:
            with self._get_session() as db:
                result = StrmRecord.delete_by_file_id(db, key)
            if result:
                logger.debug(f"STRM deleted: {key}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete STRM {key}: {e!s}")
            return False

    def get_strms_by_remote_dir(self, remote_dir: str) -> list[dict]:
        """
        根据远程目录获取STRM列表

        Args:
            remote_dir: 远程目录路径

        Returns:
            STRM记录列表
        """
        try:
            with self._get_session() as db:
                records = StrmRecord.get_by_remote_dir(db, remote_dir)
                return [r.to_dict() for r in records]
        except Exception as e:
            logger.error(f"Failed to get STRMs by remote dir {remote_dir}: {e!s}")
            return []

    def get_all_strms(self) -> list[dict]:
        """
        获取所有STRM记录

        Returns:
            STRM记录列表
        """
        try:
            with self._get_session() as db:
                records = StrmRecord.get_all(db)
                return [r.to_dict() for r in records]
        except Exception as e:
            logger.error(f"Failed to get all STRMs: {e!s}")
            return []

    def get_records(self) -> dict[str, datetime]:
        """
        获取扫描记录

        Returns:
            {remote_dir: last_scan} 字典
        """
        try:
            with self._get_session() as db:
                records = ScanRecord.get_all(db)
                return records
        except Exception as e:
            logger.error(f"Failed to get records: {e!s}")
            return {}

    def save_record(self, remote_dir: str) -> bool:
        """
        保存扫描记录

        Args:
            remote_dir: 远程目录路径

        Returns:
            是否成功
        """
        try:
            with self._get_session() as db:
                ScanRecord.create_or_update(db, remote_dir)
            logger.debug(f"Record saved: {remote_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to save record {remote_dir}: {e!s}")
            return False

    def delete_record(self, remote_dir: str) -> bool:
        """
        删除扫描记录

        Args:
            remote_dir: 远程目录路径

        Returns:
            是否成功
        """
        try:
            with self._get_session() as db:
                result = ScanRecord.delete_by_remote_dir(db, remote_dir)
            if result:
                logger.debug(f"Record deleted: {remote_dir}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete record {remote_dir}: {e!s}")
            return False

    def delete_strms_by_remote_dir(self, remote_dir: str) -> int:
        """
        删除指定远程目录下的所有STRM记录

        Args:
            remote_dir: 远程目录路径

        Returns:
            删除的记录数
        """
        try:
            with self._get_session() as db:
                count = StrmRecord.delete_by_remote_dir(db, remote_dir)
            return count
        except Exception as e:
            logger.error(f"Failed to delete STRMs by remote dir {remote_dir}: {e!s}")
            return 0

    def close(self):
        """
        关闭数据库连接

        兼容层无需手动关闭，连接池自动管理
        """
        logger.debug(f"Database compatibility layer closed: {self.db_path}")
