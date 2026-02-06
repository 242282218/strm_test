"""
LRU缓存实现模块

提供标准的LRU（Least Recently Used）缓存机制，支持TTL和统计功能
"""
import time
import threading
from collections import OrderedDict
from typing import Any, Optional, Dict, Callable
from app.core.logging import get_logger

logger = get_logger(__name__)


class LRUCache:
    """
    LRU缓存实现类
    
    特性：
    - 支持最大容量限制
    - 支持TTL（生存时间）
    - 线程安全
    - 详细的统计信息
    """
    
    def __init__(
        self,
        maxsize: int = 1000,
        ttl: Optional[int] = None,
        enable_stats: bool = True
    ):
        """
        初始化LRU缓存
        
        Args:
            maxsize: 最大缓存条目数
            ttl: 生存时间（秒），None表示永不过期
            enable_stats: 是否启用统计功能
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.enable_stats = enable_stats
        
        # 使用OrderedDict维护访问顺序
        # value stored as (value, timestamp, ttl)
        self._cache: OrderedDict[str, tuple] = OrderedDict()
        
        # 线程安全锁
        self._lock = threading.RLock()
        
        # 统计信息
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0,
            'expirations': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，不存在或过期返回None
        """
        with self._lock:
            if key not in self._cache:
                if self.enable_stats:
                    self._stats['misses'] += 1
                return None
            
            value, timestamp, entry_ttl = self._cache[key]

            # 检查是否过期（优先使用单条TTL，其次使用默认TTL）
            effective_ttl = entry_ttl if entry_ttl is not None else self.ttl
            if effective_ttl is not None and (time.time() - timestamp) > effective_ttl:
                del self._cache[key]
                if self.enable_stats:
                    self._stats['expirations'] += 1
                    self._stats['misses'] += 1
                return None
            
            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            
            if self.enable_stats:
                self._stats['hits'] += 1
            
            return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            # 如果键已存在，先删除（更新访问顺序）
            if key in self._cache:
                del self._cache[key]
            
            # 检查容量限制
            if len(self._cache) >= self.maxsize:
                # 删除最久未使用的项
                oldest_key, _ = self._cache.popitem(last=False)
                if self.enable_stats:
                    self._stats['evictions'] += 1
                logger.debug(f"Evicted LRU entry: {oldest_key}")
            
            # 添加新项（支持单条TTL）
            entry_ttl = ttl if ttl is not None else None
            self._cache[key] = (value, time.time(), entry_ttl)
            
            if self.enable_stats:
                self._stats['sets'] += 1
    
    def delete(self, key: str) -> bool:
        """
        删除缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if self.enable_stats:
                    self._stats['deletes'] += 1
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        if not self.enable_stats:
            return {}
        
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (
                self._stats['hits'] / total_requests * 100
                if total_requests > 0 else 0
            )
            
            return {
                **self._stats,
                'size': len(self._cache),
                'max_size': self.maxsize,
                'hit_rate': f"{hit_rate:.2f}%",
                'total_requests': total_requests,
                'ttl': self.ttl
            }
    
    def cleanup_expired(self) -> int:
        """
        清理过期条目
        
        Returns:
            清理的条目数
        """
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, (_, timestamp, entry_ttl) in self._cache.items():
                effective_ttl = entry_ttl if entry_ttl is not None else self.ttl
                if effective_ttl is None:
                    continue
                if (current_time - timestamp) > effective_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys and self.enable_stats:
                self._stats['expirations'] += len(expired_keys)
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
            
            return len(expired_keys)
    
    def __len__(self) -> int:
        """返回缓存大小"""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """检查键是否存在且未过期"""
        return self.get(key) is not None


class CachedFunction:
    """
    函数缓存装饰器
    
    为函数调用结果提供缓存支持
    """
    
    def __init__(
        self,
        cache: LRUCache,
        key_func: Optional[Callable] = None,
        ttl: Optional[int] = None
    ):
        """
        初始化函数缓存
        
        Args:
            cache: LRU缓存实例
            key_func: 键生成函数，None时使用参数的字符串表示
            ttl: 特定于此函数的TTL
        """
        self.cache = cache
        self.key_func = key_func
        self.ttl = ttl
    
    def __call__(self, func: Callable):
        """装饰器实现"""
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if self.key_func:
                cache_key = self.key_func(*args, **kwargs)
            else:
                # 默认键生成：函数名+参数
                import hashlib
                key_str = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
                cache_key = hashlib.md5(key_str.encode()).hexdigest()
            
            # 检查缓存
            result = self.cache.get(cache_key)
            if result is not None:
                return result
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 缓存结果
            self.cache.set(cache_key, result)
            
            return result
        
        # 复制函数元数据
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        
        return wrapper


def cached(
    cache: LRUCache,
    key_func: Optional[Callable] = None,
    ttl: Optional[int] = None
):
    """
    函数缓存装饰器便捷函数
    
    Args:
        cache: LRU缓存实例
        key_func: 键生成函数
        ttl: 特定TTL
        
    Returns:
        装饰器函数
    """
    return CachedFunction(cache, key_func, ttl)


class MultiLevelLRUCache:
    """
    多级LRU缓存
    
    实现L1（快速）和L2（大容量）两级缓存
    """
    
    def __init__(
        self,
        l1_maxsize: int = 100,
        l2_maxsize: int = 1000,
        l1_ttl: Optional[int] = 60,
        l2_ttl: Optional[int] = 3600
    ):
        """
        初始化多级缓存
        
        Args:
            l1_maxsize: L1缓存大小（快速访问）
            l2_maxsize: L2缓存大小（大容量）
            l1_ttl: L1缓存TTL
            l2_ttl: L2缓存TTL
        """
        self.l1_cache = LRUCache(maxsize=l1_maxsize, ttl=l1_ttl)
        self.l2_cache = LRUCache(maxsize=l2_maxsize, ttl=l2_ttl)
        self._lock = threading.RLock()
        
        # 统计信息
        self._stats = {
            'l1_hits': 0,
            'l2_hits': 0,
            'misses': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值（先查L1，再查L2）
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值
        """
        with self._lock:
            # 先查L1缓存
            value = self.l1_cache.get(key)
            if value is not None:
                self._stats['l1_hits'] += 1
                return value
            
            # 再查L2缓存
            value = self.l2_cache.get(key)
            if value is not None:
                self._stats['l2_hits'] += 1
                # 提升到L1缓存
                self.l1_cache.set(key, value)
                return value
            
            self._stats['misses'] += 1
            return None
    
    def set(self, key: str, value: Any) -> None:
        """
        设置缓存值（同时设置到L1和L2）
        
        Args:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            self.l1_cache.set(key, value)
            self.l2_cache.set(key, value)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取多级缓存统计
        
        Returns:
            统计信息
        """
        with self._lock:
            l1_stats = self.l1_cache.get_stats()
            l2_stats = self.l2_cache.get_stats()
            
            total_hits = self._stats['l1_hits'] + self._stats['l2_hits']
            total_requests = total_hits + self._stats['misses']
            hit_rate = (
                total_hits / total_requests * 100
                if total_requests > 0 else 0
            )
            
            return {
                'l1_hits': self._stats['l1_hits'],
                'l2_hits': self._stats['l2_hits'],
                'misses': self._stats['misses'],
                'total_hits': total_hits,
                'hit_rate': f"{hit_rate:.2f}%",
                'l1_cache': l1_stats,
                'l2_cache': l2_stats
            }


# 便捷函数和默认实例
_default_cache = None


def get_default_cache(maxsize: int = 1000, ttl: Optional[int] = 3600) -> LRUCache:
    """
    获取默认LRU缓存实例
    
    Args:
        maxsize: 最大缓存大小
        ttl: 生存时间
        
    Returns:
        LRU缓存实例
    """
    global _default_cache
    if _default_cache is None:
        _default_cache = LRUCache(maxsize=maxsize, ttl=ttl)
    return _default_cache


def clear_default_cache():
    """清空默认缓存"""
    global _default_cache
    if _default_cache:
        _default_cache.clear()
