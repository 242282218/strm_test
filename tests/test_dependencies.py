# -*- coding: utf-8 -*-
"""
服务依赖注入测试

测试服务容器和依赖注入功能
"""

import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

import app.core.dependencies as dependencies
from app.core.service_container import (
    ServiceContainer,
    ServiceLifetime,
    get_service_container,
    reset_service_container,
)
from app.core.dependencies import (
    initialize_service_container,
    override_service,
    restore_service,
    restore_all_services,
    reset_container,
    get_cache,
    get_cron,
    get_notification,
    require_api_key,
    get_admin_user,
)


class TestServiceContainer:
    """服务容器测试"""

    def setup_method(self):
        """每个测试前重置容器"""
        reset_service_container()

    def test_singleton_registration(self):
        """测试单例服务注册"""
        container = ServiceContainer()

        # 注册单例服务
        class MockService:
            def __init__(self):
                self.value = "test"

        container.add_singleton(MockService)

        # 获取两次，应该是同一个实例
        instance1 = container.get(MockService)
        instance2 = container.get(MockService)

        assert instance1 is instance2
        assert instance1.value == "test"

    def test_singleton_creation_is_thread_safe(self):
        """测试并发获取时单例只创建一次"""
        container = ServiceContainer()
        start_event = threading.Event()
        creation_lock = threading.Lock()
        creation_count = {"value": 0}
        results = []
        errors = []

        class MockService:
            pass

        def factory():
            time.sleep(0.01)
            with creation_lock:
                creation_count["value"] += 1
            return MockService()

        def worker():
            start_event.wait()
            try:
                results.append(container.get(MockService))
            except Exception as exc:  # pragma: no cover - assertion below handles failures
                errors.append(exc)

        container.add_singleton(MockService, factory=factory)
        threads = [threading.Thread(target=worker) for _ in range(8)]

        for thread in threads:
            thread.start()
        start_event.set()
        for thread in threads:
            thread.join(timeout=2)

        assert not errors
        assert len(results) == 8
        assert creation_count["value"] == 1
        assert all(instance is results[0] for instance in results)

    def test_transient_registration(self):
        """测试瞬态服务注册"""
        container = ServiceContainer()

        # 注册瞬态服务
        class MockService:
            def __init__(self):
                self.id = id(self)

        container.add_transient(MockService)

        # 获取两次，应该是不同实例
        instance1 = container.get(MockService)
        instance2 = container.get(MockService)

        assert instance1 is not instance2
        assert instance1.id != instance2.id

    def test_factory_registration(self):
        """测试工厂函数注册"""
        container = ServiceContainer()

        # 使用工厂函数创建服务
        class MockService:
            def __init__(self, value: str):
                self.value = value

        container.add_singleton(MockService, factory=lambda: MockService("factory_value"))

        instance = container.get(MockService)
        assert instance.value == "factory_value"

    def test_instance_registration(self):
        """测试实例注册"""
        container = ServiceContainer()

        # 创建并注册实例
        class MockService:
            def __init__(self):
                self.value = "instance"

        instance = MockService()
        container.add_instance(MockService, instance)

        retrieved = container.get(MockService)
        assert retrieved is instance
        assert retrieved.value == "instance"

    def test_service_override(self):
        """测试服务覆盖（测试替身）"""
        container = ServiceContainer()

        # 注册原始服务
        class MockService:
            def __init__(self):
                self.value = "original"

        container.add_singleton(MockService)

        # 获取原始实例
        original = container.get(MockService)
        assert original.value == "original"

        # 覆盖为 Mock 实例
        mock_instance = Mock()
        mock_instance.value = "mock"
        container.override(MockService, mock_instance)

        # 获取覆盖后的实例
        overridden = container.get(MockService)
        assert overridden is mock_instance
        assert overridden.value == "mock"

        # 清除覆盖
        container.clear_override(MockService)

        # 应该返回原始实例
        restored = container.get(MockService)
        assert restored is original

    def test_try_get_unregistered_service(self):
        """测试获取未注册的服务"""
        container = ServiceContainer()

        class UnregisteredService:
            pass

        result = container.try_get(UnregisteredService)
        assert result is None

    def test_get_unregistered_service_raises_error(self):
        """测试获取未注册的服务抛出异常"""
        container = ServiceContainer()

        class UnregisteredService:
            pass

        with pytest.raises(KeyError, match="Service not registered"):
            container.get(UnregisteredService)

    def test_is_registered(self):
        """测试服务注册检查"""
        container = ServiceContainer()

        class MockService:
            pass

        assert not container.is_registered(MockService)

        container.add_singleton(MockService)

        assert container.is_registered(MockService)

    def test_global_container(self):
        """测试全局容器"""
        container1 = get_service_container()
        container2 = get_service_container()

        # 应该是同一个实例
        assert container1 is container2

        # 重置后应该是新实例
        reset_service_container()
        container3 = get_service_container()

        assert container3 is not container1


class TestServiceLifecycle:
    """服务生命周期测试"""

    def setup_method(self):
        """每个测试前重置容器"""
        reset_service_container()

    @pytest.mark.asyncio
    async def test_service_start_stop(self):
        """测试服务启动和停止"""
        container = ServiceContainer()

        # 创建带 start 和 stop 方法的 Mock 服务
        class MockService:
            def __init__(self):
                self.started = False
                self.stopped = False

            async def start(self):
                self.started = True

            async def stop(self):
                self.stopped = True

        container.add_singleton(MockService)

        # 启动服务
        await container.start_services()

        instance = container.get(MockService)
        assert instance.started is True

        # 停止服务
        await container.stop_services()

        assert instance.stopped is True

    @pytest.mark.asyncio
    async def test_service_start_stop_order(self):
        """测试服务启动和停止顺序"""
        container = ServiceContainer()

        # 创建多个服务
        start_order = []
        stop_order = []

        class ServiceA:
            async def start(self):
                start_order.append("A")

            async def stop(self):
                stop_order.append("A")

        class ServiceB:
            async def start(self):
                start_order.append("B")

            async def stop(self):
                stop_order.append("B")

        container.add_singleton(ServiceA)
        container.add_singleton(ServiceB)

        # 启动服务
        await container.start_services()
        assert len(start_order) == 2

        # 停止服务（顺序应该相反）
        await container.stop_services()
        assert len(stop_order) == 2


class TestDependencyInjection:
    """依赖注入测试"""

    def setup_method(self):
        """每个测试前重置容器"""
        reset_service_container()

    def test_initialize_service_container(self):
        """测试初始化服务容器"""
        container = initialize_service_container()

        # 验证服务已注册
        from app.services.cache_service import CacheService
        from app.services.cron_service import CronService
        from app.services.notification_service import NotificationService

        assert container.is_registered(CacheService)
        assert container.is_registered(CronService)
        assert container.is_registered(NotificationService)

    def test_override_service_helper(self):
        """测试服务覆盖辅助函数"""
        from app.services.cache_service import CacheService

        # 初始化容器
        initialize_service_container()

        # 创建 Mock 实例
        mock_cache = Mock()
        mock_cache.get = AsyncMock(return_value="mock_value")

        # 覆盖服务
        override_service(CacheService, mock_cache)

        # 获取服务应该是 Mock 实例
        cache = get_cache()
        assert cache is mock_cache

        # 恢复服务
        restore_service(CacheService)

        # 应该返回原始实例
        cache = get_cache()
        assert cache is not mock_cache

    def test_restore_all_services_helper(self):
        """测试恢复所有服务辅助函数"""
        from app.services.cache_service import CacheService
        from app.services.cron_service import CronService

        # 初始化容器
        initialize_service_container()

        # 覆盖多个服务
        override_service(CacheService, Mock())
        override_service(CronService, Mock())

        # 恢复所有服务
        restore_all_services()

        # 应该返回原始实例
        cache = get_cache()
        cron = get_cron()

        # 验证不是 Mock 实例
        assert not isinstance(cache, Mock)
        assert not isinstance(cron, Mock)

    def test_reset_container_helper(self):
        """测试重置容器辅助函数"""
        from app.services.cache_service import CacheService

        # 初始化容器
        container1 = initialize_service_container()
        container1.add_singleton(CacheService)

        # 重置容器
        reset_container()

        # 获取新容器
        container2 = get_service_container()

        # 应该是新容器
        assert container2 is not container1
        assert not container2.is_registered(CacheService)

    def test_require_api_key_accepts_auth_cookie_jwt(self):
        app = FastAPI()

        @app.get("/protected")
        async def protected(_auth: None = Depends(require_api_key)):
            return {"ok": True}

        with patch.dict("os.environ", {"REQUIRE_API_KEY": "true", "API_KEY": "header-only-key"}):
            with patch("app.services.auth_service.AuthService.verify_access_token", return_value=7):
                client = TestClient(app)
                client.cookies.set("auth_token", "signed-jwt-cookie")

                response = client.get("/protected")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_require_api_key_accepts_canonical_security_env_alias(self):
        app = FastAPI()

        @app.get("/protected")
        async def protected(_auth: None = Depends(require_api_key)):
            return {"ok": True}

        with patch.dict(
            "os.environ",
            {"REQUIRE_API_KEY": "true", "SMART_MEDIA_SECURITY_API_KEY": "security-header-key"},
            clear=True,
        ):
            client = TestClient(app)
            response = client.get("/protected", headers={"X-API-Key": "security-header-key"})

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_get_admin_user_accepts_auth_cookie_jwt(self):
        app = FastAPI()
        fake_db = object()

        @app.get("/admin")
        async def admin_only(current_user=Depends(get_admin_user)):
            return {"user_id": current_user.id}

        app.dependency_overrides[dependencies.get_db] = lambda: fake_db

        admin_user = SimpleNamespace(id=7, role="admin", is_active=True)
        with patch("app.services.auth_service.AuthService.verify_access_token", return_value=7):
            with patch("app.models.user.User.get_by_id", return_value=admin_user):
                client = TestClient(app)
                client.cookies.set("auth_token", "signed-jwt-cookie")

                response = client.get("/admin")

        assert response.status_code == 200
        assert response.json() == {"user_id": 7}


class TestServiceDescriptor:
    """服务描述符测试"""

    def test_service_descriptor_repr(self):
        """测试服务描述符字符串表示"""
        from app.core.service_container import ServiceDescriptor

        class MockService:
            pass

        descriptor = ServiceDescriptor(
            service_type=MockService,
            implementation=MockService,
            lifetime=ServiceLifetime.SINGLETON,
        )

        repr_str = repr(descriptor)
        assert "MockService" in repr_str
        assert "singleton" in repr_str


class TestServiceInfo:
    """服务信息测试"""

    def setup_method(self):
        """每个测试前重置容器"""
        reset_service_container()

    def test_get_service_info(self):
        """测试获取服务信息"""
        container = ServiceContainer()

        class ServiceA:
            pass

        class ServiceB:
            pass

        container.add_singleton(ServiceA)
        container.add_instance(ServiceB, ServiceB())

        info = container.get_service_info()

        assert "ServiceA" in info["registered_services"]
        assert "ServiceB" in info["singleton_instances"]
        assert info["started"] is False
        assert info["stopped"] is False


# ==================== 测试替身示例 ====================

class MockCacheService:
    """Mock 缓存服务示例"""

    def __init__(self):
        self.data = {}
        self.get_calls = []
        self.set_calls = []

    async def get(self, key: str):
        self.get_calls.append(key)
        return self.data.get(key)

    async def set(self, key: str, value, ttl=None):
        self.set_calls.append((key, value, ttl))
        self.data[key] = value

    async def start(self):
        pass

    async def stop(self):
        pass


class TestWithMockService:
    """使用 Mock 服务的测试示例"""

    def setup_method(self):
        """每个测试前重置容器"""
        reset_service_container()

    @pytest.mark.asyncio
    async def test_with_mock_cache(self):
        """使用 Mock 缓存服务进行测试"""
        from app.services.cache_service import CacheService

        # 初始化容器
        initialize_service_container()

        # 创建并注入 Mock 服务
        mock_cache = MockCacheService()
        override_service(CacheService, mock_cache)

        # 获取服务（应该是 Mock 实例）
        cache = get_cache()
        assert isinstance(cache, MockCacheService)

        # 使用 Mock 服务进行测试
        await cache.set("test_key", "test_value")
        result = await cache.get("test_key")

        assert result == "test_value"
        assert "test_key" in [call[0] for call in mock_cache.set_calls]
        assert "test_key" in mock_cache.get_calls

        # 清理
        restore_service(CacheService)


@pytest.mark.asyncio
async def test_get_quark_cookie_prefers_env_override_over_runtime_config(monkeypatch):
    monkeypatch.setattr(dependencies, "_get_runtime_quark_config", lambda: SimpleNamespace(cookie="config-cookie"))
    monkeypatch.setattr(dependencies, "get_env_override", lambda *_args: "env-cookie")

    assert await dependencies.get_quark_cookie() == "env-cookie"


@pytest.mark.asyncio
async def test_get_quark_cookie_uses_runtime_config_when_env_missing(monkeypatch):
    monkeypatch.setattr(dependencies, "_get_runtime_quark_config", lambda: SimpleNamespace(cookie="config-cookie"))
    monkeypatch.setattr(dependencies, "get_env_override", lambda *_args: None)

    assert await dependencies.get_quark_cookie() == "config-cookie"


@pytest.mark.asyncio
async def test_get_quark_cookie_falls_back_to_placeholder_when_runtime_config_missing(monkeypatch):
    monkeypatch.setattr(dependencies, "_get_runtime_quark_config", lambda: None)
    monkeypatch.setattr(dependencies, "get_env_override", lambda *_args: None)

    assert await dependencies.get_quark_cookie() == "test_cookie"


@pytest.mark.asyncio
async def test_get_only_video_flag_uses_runtime_config(monkeypatch):
    monkeypatch.setattr(dependencies, "_get_runtime_quark_config", lambda: SimpleNamespace(only_video=False))

    assert await dependencies.get_only_video_flag() is False


@pytest.mark.asyncio
async def test_get_root_id_uses_runtime_config(monkeypatch):
    monkeypatch.setattr(dependencies, "_get_runtime_quark_config", lambda: SimpleNamespace(root_id="root-42"))

    assert await dependencies.get_root_id() == "root-42"


# ==================== pytest fixtures ====================

@pytest.fixture
def clean_container():
    """清理容器的 fixture"""
    reset_service_container()
    yield
    reset_service_container()


@pytest.fixture
def initialized_container(clean_container):
    """初始化容器的 fixture"""
    return initialize_service_container()


@pytest.fixture
def mock_cache_service():
    """Mock 缓存服务的 fixture"""
    return MockCacheService()
