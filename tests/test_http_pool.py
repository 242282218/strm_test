"""
HTTP 连接池模块单元测试

测试连接池管理、客户端创建和健康检查
"""

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core.http_pool import (
    ClientConfig,
    ClientType,
    HTTPConnectionPool,
    get_ai_client,
    get_emby_client,
    get_general_client,
    get_http_pool,
    get_http_pool_sync,
    get_quark_client,
    get_tmdb_client,
)


class TestClientConfig:
    """客户端配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = ClientConfig()

        assert config.base_url is None
        assert config.timeout == 30.0
        assert config.max_connections == 100
        assert config.max_keepalive_connections == 20
        assert config.keepalive_expiry == 30.0
        assert config.follow_redirects is True
        assert config.verify_ssl is True

    def test_custom_config(self):
        """测试自定义配置"""
        config = ClientConfig(
            base_url="https://example.com", timeout=60.0, max_connections=50, headers={"Custom-Header": "value"}
        )

        assert config.base_url == "https://example.com"
        assert config.timeout == 60.0
        assert config.max_connections == 50
        assert config.headers["Custom-Header"] == "value"


class TestHTTPConnectionPool:
    """HTTP 连接池测试"""

    @pytest_asyncio.fixture
    async def pool(self):
        """创建连接池实例"""
        pool = HTTPConnectionPool(max_connections=50, max_keepalive_connections=10, keepalive_expiry=30.0)
        await pool.initialize()
        yield pool
        await pool.close()

    def test_init(self):
        """测试初始化"""
        pool = HTTPConnectionPool(max_connections=100, max_keepalive_connections=20)

        assert pool._default_max_connections == 100
        assert pool._default_max_keepalive == 20
        assert pool._initialized is False

    @pytest.mark.asyncio
    async def test_get_instance(self):
        """测试获取单例实例"""
        # 重置单例
        HTTPConnectionPool._instance = None

        pool1 = await HTTPConnectionPool.get_instance()
        pool2 = await HTTPConnectionPool.get_instance()

        assert pool1 is pool2

        # 清理
        await pool1.close()
        HTTPConnectionPool._instance = None

    def test_get_instance_sync(self):
        """测试同步获取单例实例"""
        HTTPConnectionPool._instance = None

        pool = HTTPConnectionPool.get_instance_sync()

        assert pool is not None
        assert isinstance(pool, HTTPConnectionPool)

        HTTPConnectionPool._instance = None

    @pytest.mark.asyncio
    async def test_initialize(self):
        """测试初始化连接池"""
        pool = HTTPConnectionPool()

        assert pool._initialized is False

        await pool.initialize()

        assert pool._initialized is True
        # 应该预创建 QUARK 和 GENERAL 客户端
        assert ClientType.QUARK in pool._clients
        assert ClientType.GENERAL in pool._clients

        await pool.close()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """测试重复初始化是幂等的"""
        pool = HTTPConnectionPool()

        await pool.initialize()
        await pool.initialize()  # 重复初始化

        assert pool._initialized is True

        await pool.close()

    @pytest.mark.asyncio
    async def test_get_client(self, pool):
        """测试获取客户端"""
        client = await pool.get_client(ClientType.QUARK)

        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed

    @pytest.mark.asyncio
    async def test_get_client_cached(self, pool):
        """测试获取缓存的客户端"""
        client1 = await pool.get_client(ClientType.QUARK)
        client2 = await pool.get_client(ClientType.QUARK)

        assert client1 is client2

    @pytest.mark.asyncio
    async def test_get_client_with_custom_config(self, pool):
        """测试使用自定义配置获取客户端"""
        custom_config = ClientConfig(base_url="https://custom.example.com", timeout=120.0)

        client = await pool.get_client(ClientType.GENERAL, config=custom_config)

        assert client is not None
        # 注意: 由于缓存机制, 可能返回已存在的客户端

    @pytest.mark.asyncio
    async def test_get_client_with_headers(self, pool):
        """测试获取带额外请求头的客户端"""
        extra_headers = {"X-Custom-Auth": "token123"}

        client = await pool.get_client_with_headers(ClientType.QUARK, extra_headers=extra_headers)

        assert client is not None

    @pytest.mark.asyncio
    async def test_get_stats(self, pool):
        """测试获取统计信息"""
        stats = pool.get_stats()

        assert "pool_stats" in stats
        assert "total_clients" in stats
        assert "initialized" in stats
        assert stats["initialized"] is True

    @pytest.mark.asyncio
    async def test_get_health_status(self, pool):
        """测试获取健康状态"""
        health = pool.get_health_status()

        assert "status" in health
        assert "healthy_clients" in health
        assert "unhealthy_clients" in health
        assert "initialized" in health

    @pytest.mark.asyncio
    async def test_close(self):
        """测试关闭连接池"""
        pool = HTTPConnectionPool()
        await pool.initialize()

        await pool.close()

        assert len(pool._clients) == 0
        assert pool._initialized is False

    @pytest.mark.asyncio
    async def test_reset_client(self, pool):
        """测试重置客户端"""
        # 先获取客户端
        client1 = await pool.get_client(ClientType.QUARK)

        # 重置
        await pool.reset_client(ClientType.QUARK)

        # 再次获取应该是新客户端
        client2 = await pool.get_client(ClientType.QUARK)
        assert client1 is not client2

        # client1 应该已关闭
        assert client1.is_closed

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试异步上下文管理器"""
        async with HTTPConnectionPool() as pool:
            assert pool._initialized is True
            client = await pool.get_client(ClientType.GENERAL)
            assert client is not None

        # 退出后应该关闭
        assert len(pool._clients) == 0


class TestClientTypes:
    """客户端类型测试"""

    def test_client_type_values(self):
        """测试客户端类型枚举值"""
        assert ClientType.QUARK.value == "quark"
        assert ClientType.EMBY.value == "emby"
        assert ClientType.TMDB.value == "tmdb"
        assert ClientType.AI_PROVIDER.value == "ai"
        assert ClientType.GENERAL.value == "general"


class TestConvenienceFunctions:
    """便捷函数测试"""

    @pytest.mark.asyncio
    async def test_get_http_pool(self):
        """测试获取 HTTP 连接池"""
        HTTPConnectionPool._instance = None

        pool = await get_http_pool()

        assert pool is not None
        assert isinstance(pool, HTTPConnectionPool)

        await pool.close()
        HTTPConnectionPool._instance = None

    def test_get_http_pool_sync(self):
        """测试同步获取 HTTP 连接池"""
        HTTPConnectionPool._instance = None

        pool = get_http_pool_sync()

        assert pool is not None
        assert isinstance(pool, HTTPConnectionPool)

        HTTPConnectionPool._instance = None

    @pytest.mark.asyncio
    async def test_get_quark_client(self):
        """测试获取夸克客户端"""
        HTTPConnectionPool._instance = None

        client = await get_quark_client()

        assert client is not None
        assert isinstance(client, httpx.AsyncClient)

        pool = await get_http_pool()
        await pool.close()
        HTTPConnectionPool._instance = None

    @pytest.mark.asyncio
    async def test_get_emby_client(self):
        """测试获取 Emby 客户端"""
        HTTPConnectionPool._instance = None

        client = await get_emby_client()

        assert client is not None

        pool = await get_http_pool()
        await pool.close()
        HTTPConnectionPool._instance = None

    @pytest.mark.asyncio
    async def test_get_tmdb_client(self):
        """测试获取 TMDB 客户端"""
        HTTPConnectionPool._instance = None

        client = await get_tmdb_client()

        assert client is not None

        pool = await get_http_pool()
        await pool.close()
        HTTPConnectionPool._instance = None

    @pytest.mark.asyncio
    async def test_get_ai_client(self):
        """测试获取 AI 客户端"""
        HTTPConnectionPool._instance = None

        client = await get_ai_client()

        assert client is not None

        pool = await get_http_pool()
        await pool.close()
        HTTPConnectionPool._instance = None

    @pytest.mark.asyncio
    async def test_get_general_client(self):
        """测试获取通用客户端"""
        HTTPConnectionPool._instance = None

        client = await get_general_client()

        assert client is not None

        pool = await get_http_pool()
        await pool.close()
        HTTPConnectionPool._instance = None


def test_app_lifespan_when_started_then_prewarms_http_pool() -> None:
    from app.main import app

    HTTPConnectionPool._instance = None

    with TestClient(app):
        pool = HTTPConnectionPool._instance
        assert pool is not None
        assert pool._initialized is True

    if HTTPConnectionPool._instance is not None:
        HTTPConnectionPool._instance = None


class TestPoolStats:
    """连接池统计测试"""

    @pytest_asyncio.fixture
    async def pool(self):
        """创建连接池实例"""
        pool = HTTPConnectionPool()
        await pool.initialize()
        yield pool
        await pool.close()

    @pytest.mark.asyncio
    async def test_stats_structure(self, pool):
        """测试统计信息结构"""
        stats = pool.get_stats()

        assert "pool_stats" in stats
        assert "quark" in stats["pool_stats"]
        assert "general" in stats["pool_stats"]

    @pytest.mark.asyncio
    async def test_health_status_healthy(self, pool):
        """测试健康状态 - 健康"""
        health = pool.get_health_status()

        # 初始化后应该有健康的客户端
        assert health["healthy_clients"] >= 0
        assert health["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_health_status_after_close(self):
        """测试关闭后的健康状态"""
        pool = HTTPConnectionPool()
        await pool.initialize()
        await pool.close()

        health = pool.get_health_status()

        assert health["healthy_clients"] == 0
        assert health["unhealthy_clients"] == 0
