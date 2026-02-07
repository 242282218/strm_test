# -*- coding: utf-8 -*-
"""
磁盘缓存实现 - 基于 SQLite

提供持久化的缓存存储，服务重启后缓存不丢失
适用于存储直链等需要持久化的数据

特性：
- SQLite 持久化存储
- 自动过期清理
- 支持 JSON 和 Pickle 序列化
- 异步操作支持
- 与内存缓存协同工作 (L1/L2 缓存架构)
"""

import json
import pickle
import sqlite3
import asyncio
import aiosqlite
from typing import Any, Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from app.core.logging import get_logger

logger = get_logger(__name__)


class DiskCache:
    """
    基于 SQLite 的磁盘缓存
    
    作为 L2 缓存，与内存 L1 缓存配合使用
    """
    
    def __init__(
        self,
        db_path: str = "cache/cache.db",
        default_ttl: int = 3600,
        cleanup_interval: int = 3600  # 每小时清理一次
    ):
        """
        初始化磁盘缓存
        
        Args:
            db_path: SQLite 数据库路径
            default_ttl: 默认过期时间（秒）
            cleanup_interval: 清理间隔（秒）
        """
        self.db_path = Path(db_path)
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self._lock = asyncio.Lock()
        
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_db()
        
        # 启动清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"DiskCache initialized: db_path={db_path}, default_ttl={default_ttl}s")
    
    def _init_db(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    value_type TEXT NOT NULL DEFAULT 'json',
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    access_count INTEGER DEFAULT 0,
                    last_access REAL
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at 
                ON cache_entries(expires_at) 
                WHERE expires_at IS NOT NULL
            """)
            
            conn.commit()
    
    async def start(self):
        """启动缓存服务（包括定期清理）"""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info("DiskCache started with periodic cleanup")
    
    async def stop(self):
        """停止缓存服务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("DiskCache stopped")
    
    async def _periodic_cleanup(self):
        """定期清理过期条目"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                deleted = await self.cleanup_expired()
                if deleted > 0:
                    logger.debug(f"DiskCache cleanup: removed {deleted} expired entries")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DiskCache cleanup error: {e}")
    
    def _serialize(self, value: Any) -> Tuple[bytes, str]:
        """
        序列化值
        
        Returns:
            (序列化后的字节, 类型标识)
        """
        try:
            # 优先使用 JSON（人类可读）
            return json.dumps(value, ensure_ascii=False).encode('utf-8'), 'json'
        except (TypeError, ValueError):
            # 复杂对象使用 Pickle
            return pickle.dumps(value), 'pickle'
    
    def _deserialize(self, data: bytes, value_type: str) -> Any:
        """反序列化值"""
        if value_type == 'json':
            return json.loads(data.decode('utf-8'))
        else:
            return pickle.loads(data)
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，不存在或已过期返回 None
        """
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute(
                        "SELECT value, value_type, expires_at FROM cache_entries WHERE key = ?",
                        (key,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        
                        if row is None:
                            return None
                        
                        value_data, value_type, expires_at = row
                        
                        # 检查是否过期
                        if expires_at is not None and datetime.now().timestamp() > expires_at:
                            # 删除过期条目
                            await db.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                            await db.commit()
                            return None
                        
                        # 更新访问统计
                        await db.execute(
                            """UPDATE cache_entries 
                               SET access_count = access_count + 1, 
                                   last_access = ? 
                               WHERE key = ?""",
                            (datetime.now().timestamp(), key)
                        )
                        await db.commit()
                        
                        return self._deserialize(value_data, value_type)
                        
            except Exception as e:
                logger.error(f"DiskCache GET failed for key {key}: {e}")
                return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 表示永不过期
            
        Returns:
            设置是否成功
        """
        async with self._lock:
            try:
                value_data, value_type = self._serialize(value)
                created_at = datetime.now().timestamp()
                expires_at = None
                
                if ttl is not None and ttl > 0:
                    expires_at = created_at + ttl
                elif self.default_ttl > 0:
                    expires_at = created_at + self.default_ttl
                
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        """INSERT OR REPLACE INTO cache_entries 
                           (key, value, value_type, created_at, expires_at, last_access)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (key, value_data, value_type, created_at, expires_at, created_at)
                    )
                    await db.commit()
                    
                return True
                
            except Exception as e:
                logger.error(f"DiskCache SET failed for key {key}: {e}")
                return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "DELETE FROM cache_entries WHERE key = ?",
                        (key,)
                    )
                    await db.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"DiskCache DELETE failed for key {key}: {e}")
                return False
    
    async def clear(self) -> bool:
        """清空所有缓存"""
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("DELETE FROM cache_entries")
                    await db.commit()
                    return True
            except Exception as e:
                logger.error(f"DiskCache CLEAR failed: {e}")
                return False
    
    async def cleanup_expired(self) -> int:
        """
        清理过期条目
        
        Returns:
            删除的条目数
        """
        async with self._lock:
            try:
                now = datetime.now().timestamp()
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at < ?",
                        (now,)
                    )
                    await db.commit()
                    return cursor.rowcount
            except Exception as e:
                logger.error(f"DiskCache cleanup_expired failed: {e}")
                return 0
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在且未过期"""
        async with self._lock:
            try:
                now = datetime.now().timestamp()
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute(
                        """SELECT 1 FROM cache_entries 
                           WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)""",
                        (key, now)
                    ) as cursor:
                        return await cursor.fetchone() is not None
            except Exception as e:
                logger.error(f"DiskCache EXISTS failed for key {key}: {e}")
                return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    # 总条目数
                    async with db.execute("SELECT COUNT(*) FROM cache_entries") as cursor:
                        total = (await cursor.fetchone())[0]
                    
                    # 过期条目数
                    now = datetime.now().timestamp()
                    async with db.execute(
                        "SELECT COUNT(*) FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at < ?",
                        (now,)
                    ) as cursor:
                        expired = (await cursor.fetchone())[0]
                    
                    # 数据库文件大小
                    db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                    
                    return {
                        'total_entries': total,
                        'expired_entries': expired,
                        'db_size_bytes': db_size,
                        'db_size_mb': round(db_size / (1024 * 1024), 2),
                        'db_path': str(self.db_path)
                    }
            except Exception as e:
                logger.error(f"DiskCache get_stats failed: {e}")
                return {'error': str(e)}
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        批量获取缓存值
        
        Args:
            keys: 键列表
            
        Returns:
            {key: value} 字典
        """
        if not keys:
            return {}
        
        results = {}
        now = datetime.now().timestamp()
        
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    placeholders = ','.join('?' * len(keys))
                    
                    async with db.execute(
                        f"""SELECT key, value, value_type, expires_at 
                            FROM cache_entries 
                            WHERE key IN ({placeholders})""",
                        keys
                    ) as cursor:
                        rows = await cursor.fetchall()
                    
                    expired_keys = []
                    
                    for row in rows:
                        key, value_data, value_type, expires_at = row
                        
                        # 检查过期
                        if expires_at is not None and now > expires_at:
                            expired_keys.append(key)
                            continue
                        
                        try:
                            results[key] = self._deserialize(value_data, value_type)
                        except Exception as e:
                            logger.warning(f"Failed to deserialize cache entry {key}: {e}")
                    
                    # 删除过期条目
                    if expired_keys:
                        placeholders = ','.join('?' * len(expired_keys))
                        await db.execute(
                            f"DELETE FROM cache_entries WHERE key IN ({placeholders})",
                            expired_keys
                        )
                        await db.commit()
                    
                    return results
                    
            except Exception as e:
                logger.error(f"DiskCache get_many failed: {e}")
                return {}
    
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> int:
        """
        批量设置缓存值
        
        Args:
            items: {key: value} 字典
            ttl: 过期时间（秒）
            
        Returns:
            成功设置的条目数
        """
        if not items:
            return 0
        
        created_at = datetime.now().timestamp()
        expires_at = None
        
        if ttl is not None and ttl > 0:
            expires_at = created_at + ttl
        elif self.default_ttl > 0:
            expires_at = created_at + self.default_ttl
        
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    success_count = 0
                    
                    for key, value in items.items():
                        try:
                            value_data, value_type = self._serialize(value)
                            await db.execute(
                                """INSERT OR REPLACE INTO cache_entries 
                                   (key, value, value_type, created_at, expires_at, last_access)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (key, value_data, value_type, created_at, expires_at, created_at)
                            )
                            success_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to serialize cache entry {key}: {e}")
                    
                    await db.commit()
                    return success_count
                    
            except Exception as e:
                logger.error(f"DiskCache set_many failed: {e}")
                return 0


# 全局实例
_global_disk_cache: Optional[DiskCache] = None


def get_disk_cache(
    db_path: str = "cache/cache.db",
    default_ttl: int = 3600
) -> DiskCache:
    """获取全局磁盘缓存实例"""
    global _global_disk_cache
    
    if _global_disk_cache is None:
        _global_disk_cache = DiskCache(
            db_path=db_path,
            default_ttl=default_ttl
        )
    
    return _global_disk_cache
