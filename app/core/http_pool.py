"""
HTTP 连接池管理器

提供全局 HTTP 客户端连接池，实现连接复用，降低延迟和内存占用。

特性:
- 单例模式，全局共享连接池
- 按服务名称区分不同客户端配置
- 自动连接复用和 keep-alive 管理
- 健康检查和监控接口
- 优雅关闭

性能优化:
- TCP 连接复用，避免重复三次握手
- 连接池预热，减少冷启动延迟
- 统一管理，降低内存占用
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx

from app.core.logging import get_logger


logger = get_logger(__name__)


class ClientType(Enum):
    """HTTP 客户端类型"""

    QUARK = "quark"  # 夸克 API 客户端
    EMBY = "emby"  # Emby 服务客户端
    TMDB = "tmdb"  # TMDB API 客户端
    AI_PROVIDER = "ai"  # AI 服务客户端
    GENERAL = "general"  # 通用客户端
    TELEGRAM = "telegram"  # Telegram Bot API 客户端
    WECHAT = "wechat"  # 微信/Server酱 API 客户端
    SCRAPE = "scrape"  # 爬虫/刮削客户端
    AI_PARSER = "ai_parser"  # AI 解析服务客户端


@dataclass
class ClientConfig:
    """客户端配置"""

    base_url: str | None = None
    timeout: float = 30.0
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)
    follow_redirects: bool = True
    verify_ssl: bool = True


# 预定义客户端配置
CLIENT_CONFIGS: dict[ClientType, ClientConfig] = {
    ClientType.QUARK: ClientConfig(
        base_url="https://pan.quark.cn",
        timeout=30.0,
        max_connections=100,
        max_keepalive_connections=30,
        keepalive_expiry=60.0,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        },
        follow_redirects=True,
    ),
    ClientType.EMBY: ClientConfig(
        timeout=30.0,
        max_connections=50,
        max_keepalive_connections=20,
        keepalive_expiry=60.0,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        follow_redirects=True,
    ),
    ClientType.TMDB: ClientConfig(
        base_url="https://api.themoviedb.org/3",
        timeout=30.0,
        max_connections=50,
        max_keepalive_connections=20,
        keepalive_expiry=60.0,
        headers={
            "Accept": "application/json",
        },
        follow_redirects=True,
    ),
    ClientType.AI_PROVIDER: ClientConfig(
        timeout=60.0,
        max_connections=30,
        max_keepalive_connections=10,
        keepalive_expiry=30.0,
        headers={
            "Content-Type": "application/json",
        },
        follow_redirects=True,
    ),
    ClientType.GENERAL: ClientConfig(
        timeout=30.0,
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=30.0,
        follow_redirects=True,
    ),
    ClientType.TELEGRAM: ClientConfig(
        base_url="https://api.telegram.org",
        timeout=30.0,
        max_connections=30,
        max_keepalive_connections=10,
        keepalive_expiry=60.0,
        headers={
            "Content-Type": "application/json",
        },
        follow_redirects=True,
    ),
    ClientType.WECHAT: ClientConfig(
        timeout=30.0,
        max_connections=30,
        max_keepalive_connections=10,
        keepalive_expiry=60.0,
        headers={
            "Content-Type": "application/json",
        },
        follow_redirects=True,
    ),
    ClientType.SCRAPE: ClientConfig(
        timeout=30.0,
        max_connections=50,
        max_keepalive_connections=20,
        keepalive_expiry=60.0,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        follow_redirects=True,
    ),
    ClientType.AI_PARSER: ClientConfig(
        timeout=60.0,
        max_connections=30,
        max_keepalive_connections=10,
        keepalive_expiry=30.0,
        headers={
            "Content-Type": "application/json",
        },
        follow_redirects=True,
    ),
}


@dataclass
class PoolStats:
    """连接池统计信息"""

    client_type: ClientType
    total_requests: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_request_at: datetime | None = None


class HTTPConnectionPool:
    """
    HTTP 连接池管理器

    单例模式，全局共享连接池，支持按服务名称区分不同客户端。

    使用示例:
        pool = HTTPConnectionPool.get_instance()

        # 获取夸克客户端
        client = await pool.get_client(ClientType.QUARK)
        response = await client.get("https://pan.quark.cn/api/...")

        # 获取统计信息
        stats = pool.get_stats()
    """

    _instance: Optional["HTTPConnectionPool"] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        keepalive_expiry: float = 30.0,
    ):
        """
        初始化连接池

        Args:
            max_connections: 最大连接数
            max_keepalive_connections: 最大 keep-alive 连接数
            keepalive_expiry: keep-alive 过期时间（秒）
        """
        self._default_max_connections = max_connections
        self._default_max_keepalive = max_keepalive_connections
        self._default_keepalive_expiry = keepalive_expiry

        # 客户端缓存
        self._clients: dict[ClientType, httpx.AsyncClient] = {}

        # 统计信息
        self._stats: dict[ClientType, PoolStats] = {ct: PoolStats(client_type=ct) for ct in ClientType}

        # 是否已初始化
        self._initialized = False
        self._init_lock = asyncio.Lock()

        logger.info(
            f"HTTPConnectionPool created: max_connections={max_connections}, "
            f"max_keepalive={max_keepalive_connections}, expiry={keepalive_expiry}s"
        )

    @classmethod
    async def get_instance(cls) -> "HTTPConnectionPool":
        """
        获取单例实例

        Returns:
            HTTPConnectionPool 实例
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        # initialize 内部有自己的 _init_lock，不能在 cls._lock 内调用（会死锁）
        if not cls._instance._initialized:
            await cls._instance.initialize()
        return cls._instance

    @classmethod
    def get_instance_sync(cls) -> "HTTPConnectionPool":
        """
        同步获取单例实例（用于非异步上下文）

        注意：首次调用时不会初始化客户端，需要后续调用 initialize()

        Returns:
            HTTPConnectionPool 实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """
        初始化连接池

        预创建常用客户端，减少冷启动延迟
        """
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            # 预创建常用客户端
            for client_type in [
                ClientType.QUARK,
                ClientType.GENERAL,
                ClientType.TMDB,
                ClientType.EMBY,
                ClientType.AI_PARSER,
            ]:
                try:
                    await self._create_client(client_type)
                    logger.debug(f"Pre-created HTTP client: {client_type.value}")
                except Exception as e:
                    logger.warning(f"Failed to pre-create client {client_type.value}: {e}")

            self._initialized = True
            logger.info("HTTPConnectionPool initialized")

    async def _create_client(
        self,
        client_type: ClientType,
        config: ClientConfig | None = None,
    ) -> httpx.AsyncClient:
        """
        创建 HTTP 客户端

        Args:
            client_type: 客户端类型
            config: 客户端配置（可选，默认使用预定义配置）

        Returns:
            httpx.AsyncClient 实例
        """
        if config is None:
            config = CLIENT_CONFIGS.get(client_type, CLIENT_CONFIGS[ClientType.GENERAL])

        # 创建连接池
        limits = httpx.Limits(
            max_connections=config.max_connections,
            max_keepalive_connections=config.max_keepalive_connections,
            keepalive_expiry=config.keepalive_expiry,
        )

        # 创建超时配置
        timeout = httpx.Timeout(
            connect=10.0,
            read=config.timeout,
            write=config.timeout,
            pool=5.0,
        )

        # 创建客户端
        # httpx 不接受 base_url=None，因此仅在配置了 base_url 时传入该参数
        client_kwargs: dict[str, Any] = {
            "timeout": timeout,
            "limits": limits,
            "headers": config.headers,
            "follow_redirects": config.follow_redirects,
            "verify": config.verify_ssl,
            "http2": False,  # HTTP/2 与夸克 CDN 不兼容，会导致请求 hang
        }
        if config.base_url:
            client_kwargs["base_url"] = config.base_url

        client = httpx.AsyncClient(**client_kwargs)

        self._clients[client_type] = client
        self._stats[client_type].created_at = datetime.now()

        logger.info(
            f"Created HTTP client: {client_type.value}, "
            f"max_connections={config.max_connections}, "
            f"max_keepalive={config.max_keepalive_connections}"
        )

        return client

    async def get_client(
        self,
        client_type: ClientType,
        config: ClientConfig | None = None,
    ) -> httpx.AsyncClient:
        """
        获取 HTTP 客户端

        如果客户端不存在，会自动创建。

        Args:
            client_type: 客户端类型
            config: 客户端配置（可选）

        Returns:
            httpx.AsyncClient 实例
        """
        # 如果客户端已存在且未关闭，直接返回
        if client_type in self._clients:
            client = self._clients[client_type]
            if not client.is_closed:
                self._stats[client_type].last_request_at = datetime.now()
                return client

        # 创建新客户端
        async with self._lock:
            # 双重检查
            if client_type in self._clients and not self._clients[client_type].is_closed:
                return self._clients[client_type]

            return await self._create_client(client_type, config)

    async def get_client_with_headers(
        self,
        client_type: ClientType,
        extra_headers: dict[str, str],
        config: ClientConfig | None = None,
    ) -> httpx.AsyncClient:
        """
        获取带有额外请求头的 HTTP 客户端

        注意：此方法会创建新的客户端实例，用于需要特殊请求头的场景。
        一般情况下应使用 get_client() 并在请求时传入 headers。

        Args:
            client_type: 客户端类型
            extra_headers: 额外的请求头
            config: 客户端配置（可选）

        Returns:
            httpx.AsyncClient 实例
        """
        if config is None:
            config = CLIENT_CONFIGS.get(client_type, CLIENT_CONFIGS[ClientType.GENERAL])

        # 合并请求头
        merged_headers = {**config.headers, **extra_headers}

        # 创建新配置
        new_config = ClientConfig(
            base_url=config.base_url,
            timeout=config.timeout,
            max_connections=config.max_connections,
            max_keepalive_connections=config.max_keepalive_connections,
            keepalive_expiry=config.keepalive_expiry,
            headers=merged_headers,
            follow_redirects=config.follow_redirects,
            verify_ssl=config.verify_ssl,
        )

        return await self._create_client(client_type, new_config)

    def get_stats(self) -> dict[str, Any]:
        """
        获取连接池统计信息

        Returns:
            统计信息字典
        """
        stats = {}

        for client_type, pool_stats in self._stats.items():
            client = self._clients.get(client_type)

            # 获取连接池状态
            if client and hasattr(client, "_transport"):
                transport = client._transport
                if hasattr(transport, "_pool"):
                    pool = transport._pool
                    pool_stats.active_connections = getattr(pool, "_active_connections", 0)
                    pool_stats.idle_connections = len(getattr(pool, "_idle_connections", []))

            stats[client_type.value] = {
                "total_requests": pool_stats.total_requests,
                "active_connections": pool_stats.active_connections,
                "idle_connections": pool_stats.idle_connections,
                "created_at": pool_stats.created_at.isoformat() if pool_stats.created_at else None,
                "last_request_at": pool_stats.last_request_at.isoformat() if pool_stats.last_request_at else None,
                "is_closed": client.is_closed if client else True,
            }

        return {
            "pool_stats": stats,
            "total_clients": len(self._clients),
            "initialized": self._initialized,
        }

    def get_health_status(self) -> dict[str, Any]:
        """
        获取健康状态

        Returns:
            健康状态字典
        """
        healthy_clients = 0
        unhealthy_clients = 0

        for client_type, client in self._clients.items():
            if client and not client.is_closed:
                healthy_clients += 1
            else:
                unhealthy_clients += 1

        return {
            "status": "healthy" if unhealthy_clients == 0 else "degraded",
            "healthy_clients": healthy_clients,
            "unhealthy_clients": unhealthy_clients,
            "initialized": self._initialized,
        }

    async def close(self) -> None:
        """
        关闭所有客户端连接

        优雅关闭所有 HTTP 客户端，释放资源
        """
        async with self._lock:
            for client_type, client in self._clients.items():
                if client and not client.is_closed:
                    try:
                        await client.aclose()
                        logger.info(f"Closed HTTP client: {client_type.value}")
                    except Exception as e:
                        logger.warning(f"Error closing client {client_type.value}: {e}")

            self._clients.clear()
            self._initialized = False
            logger.info("HTTPConnectionPool closed")

    async def reset_client(self, client_type: ClientType) -> None:
        """
        重置指定客户端

        关闭并重新创建客户端，用于处理连接问题

        Args:
            client_type: 客户端类型
        """
        async with self._lock:
            # 关闭旧客户端
            if client_type in self._clients:
                client = self._clients[client_type]
                if client and not client.is_closed:
                    try:
                        await client.aclose()
                        logger.info(f"Reset HTTP client: {client_type.value}")
                    except Exception as e:
                        logger.warning(f"Error resetting client {client_type.value}: {e}")

                del self._clients[client_type]

    async def __aenter__(self) -> "HTTPConnectionPool":
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.close()


# 全局单例访问函数
async def get_http_pool() -> HTTPConnectionPool:
    """
    获取全局 HTTP 连接池实例

    Returns:
        HTTPConnectionPool 实例
    """
    return await HTTPConnectionPool.get_instance()


def get_http_pool_sync() -> HTTPConnectionPool:
    """
    同步获取全局 HTTP 连接池实例

    Returns:
        HTTPConnectionPool 实例
    """
    return HTTPConnectionPool.get_instance_sync()


# 便捷函数
async def get_quark_client() -> httpx.AsyncClient:
    """获取夸克 API 客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.QUARK)


async def get_emby_client() -> httpx.AsyncClient:
    """获取 Emby 服务客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.EMBY)


async def get_tmdb_client() -> httpx.AsyncClient:
    """获取 TMDB API 客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.TMDB)


async def get_ai_client() -> httpx.AsyncClient:
    """获取 AI 服务客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.AI_PROVIDER)


async def get_general_client() -> httpx.AsyncClient:
    """获取通用 HTTP 客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.GENERAL)


async def get_telegram_client() -> httpx.AsyncClient:
    """获取 Telegram Bot API 客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.TELEGRAM)


async def get_wechat_client() -> httpx.AsyncClient:
    """获取微信/Server酱 API 客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.WECHAT)


async def get_scrape_client() -> httpx.AsyncClient:
    """获取爬虫/刮削客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.SCRAPE)


async def get_ai_parser_client() -> httpx.AsyncClient:
    """获取 AI 解析服务客户端"""
    pool = await get_http_pool()
    return await pool.get_client(ClientType.AI_PARSER)
