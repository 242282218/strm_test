"""
数据库模块

参考: AlistAutoStrm BoltDB操作 (strm.go:49-57)
"""

import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict
from datetime import datetime
from app.core.logging import get_logger
from app.services.config_service import get_config_service

logger = get_logger(__name__)


class Database:
    """
    数据库管理类

    参考: AlistAutoStrm BoltDB操作
    """

    def __init__(self, db_path: str):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = resolve_db_path(db_path)
        self._init_db()
        logger.info(f"Database initialized: {db_path}")

    def _init_db(self):
        """初始化数据库表结构"""
        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strm (
                    key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    local_dir TEXT NOT NULL,
                    remote_dir TEXT NOT NULL,
                    raw_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_strm_remote_dir ON strm(remote_dir)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    remote_dir TEXT PRIMARY KEY,
                    last_scan TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.debug("Database tables created/verified")

    @contextmanager
    def get_conn(self):
        """
        获取数据库连接

        Yields:
            sqlite3连接对象
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

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
            with self.get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO strm (key, name, local_dir, remote_dir, raw_url, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (key, name, local_dir, remote_dir, raw_url))
                conn.commit()
                logger.debug(f"STRM saved: {key}")
                return True
        except Exception as e:
            logger.error(f"Failed to save STRM {key}: {str(e)}")
            return False

    def get_strm(self, key: str) -> Optional[Dict]:
        """
        获取STRM记录

        Args:
            key: STRM唯一键

        Returns:
            STRM记录字典，不存在返回None
        """
        try:
            with self.get_conn() as conn:
                cursor = conn.execute("SELECT * FROM strm WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get STRM {key}: {str(e)}")
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
            with self.get_conn() as conn:
                conn.execute("DELETE FROM strm WHERE key = ?", (key,))
                conn.commit()
                logger.debug(f"STRM deleted: {key}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete STRM {key}: {str(e)}")
            return False

    def get_strms_by_remote_dir(self, remote_dir: str) -> List[Dict]:
        """
        根据远程目录获取STRM列表

        Args:
            remote_dir: 远程目录路径

        Returns:
            STRM记录列表
        """
        try:
            with self.get_conn() as conn:
                cursor = conn.execute("SELECT * FROM strm WHERE remote_dir = ?", (remote_dir,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get STRMs by remote dir {remote_dir}: {str(e)}")
            return []

    def get_all_strms(self) -> List[Dict]:
        """
        获取所有STRM记录

        Returns:
            STRM记录列表
        """
        try:
            with self.get_conn() as conn:
                cursor = conn.execute("SELECT * FROM strm")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get all STRMs: {str(e)}")
            return []

    def get_records(self) -> Dict[str, datetime]:
        """
        获取扫描记录

        Returns:
            {remote_dir: last_scan} 字典
        """
        try:
            with self.get_conn() as conn:
                cursor = conn.execute("SELECT * FROM records")
                return {row['remote_dir']: row['last_scan'] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Failed to get records: {str(e)}")
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
            with self.get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO records (remote_dir, last_scan)
                    VALUES (?, CURRENT_TIMESTAMP)
                """, (remote_dir,))
                conn.commit()
                logger.debug(f"Record saved: {remote_dir}")
                return True
        except Exception as e:
            logger.error(f"Failed to save record {remote_dir}: {str(e)}")
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
            with self.get_conn() as conn:
                conn.execute("DELETE FROM records WHERE remote_dir = ?", (remote_dir,))
                conn.commit()
                logger.debug(f"Record deleted: {remote_dir}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete record {remote_dir}: {str(e)}")
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
            with self.get_conn() as conn:
                cursor = conn.execute("DELETE FROM strm WHERE remote_dir = ?", (remote_dir,))
                conn.commit()
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} STRMs from {remote_dir}")
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete STRMs by remote dir {remote_dir}: {str(e)}")
            return 0

    def close(self):
        """
        关闭数据库连接

        由于使用上下文管理器，此方法主要用于兼容性
        """
        logger.debug(f"Database connection closed: {self.db_path}")



def resolve_db_path(db_path: Optional[str] = None) -> str:
    """
    ?????????

    ??: ??SQLite???????
    ??:
        - db_path (Optional[str]): ????????
    ??:
        - str: ?????????
    ???:
        - ??data?????????????
    """
    if not db_path:
        config = get_config_service().get_config()
        db_path = config.database
    if os.path.isabs(db_path):
        return str(Path(db_path).resolve())
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return str((data_dir / db_path).resolve())
