"""
服务容器模块

提供统一的服务依赖注入体系，支持：
- 服务生命周期管理（singleton, transient, scoped）
- 服务注册和解析
- 测试替身支持
- 异步服务启动/停止

参考：Dependency Injection 最佳实践
"""

import threading
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar
from weakref import WeakKeyDictionary

from app.core.logging import get_logger


logger = get_logger(__name__)

T = TypeVar("T")


class ServiceLifetime(Enum):
    """服务生命周期"""

    SINGLETON = "singleton"  # 单例：整个应用生命周期内只创建一次
    TRANSIENT = "transient"  # 瞬态：每次请求都创建新实例
    SCOPED = "scoped"  # 作用域：在同一作用域内共享实例


class ServiceDescriptor:
    """服务描述符"""

    def __init__(
        self,
        service_type: type,
        implementation: type | Callable | object,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
        factory: Callable | None = None,
    ):
        """
        初始化服务描述符

        Args:
            service_type: 服务类型（通常是接口或基类）
            implementation: 实现类型或工厂函数或实例
            lifetime: 服务生命周期
            factory: 可选的工厂函数
        """
        self.service_type = service_type
        self.implementation = implementation
        self.lifetime = lifetime
        self.factory = factory
        self._instance: Any | None = None

    def __repr__(self) -> str:
        return f"ServiceDescriptor({self.service_type.__name__}, lifetime={self.lifetime.value})"


class ServiceContainer:
    """
    服务容器

    管理服务的注册、解析和生命周期

    使用示例：
        container = ServiceContainer()

        # 注册服务
        container.add_singleton(ICacheService, CacheService)
        container.add_singleton(CacheService)  # 直接注册实现类

        # 使用工厂函数
        container.add_singleton(
            QuarkService,
            factory=lambda: QuarkService(cookie="...")
        )

        # 解析服务
        cache = container.get(ICacheService)
        cache = container.get(CacheService)  # 或直接获取实现类

        # 测试替身
        container.override(ICacheService, MockCacheService())
    """

    def __init__(self):
        """初始化服务容器"""
        self._services: dict[type, ServiceDescriptor] = {}
        self._instances: dict[type, Any] = {}
        self._overrides: dict[type, Any] = {}
        self._lock = threading.RLock()
        self._started = False
        self._stopped = False

        # 作用域支持（用于测试环境）
        self._scope_instances: WeakKeyDictionary = WeakKeyDictionary()

        logger.debug("ServiceContainer initialized")

    def register(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
        factory: Callable[..., T] | None = None,
    ) -> "ServiceContainer":
        """
        注册服务

        Args:
            service_type: 服务类型
            implementation: 实现类型（可选，默认为 service_type）
            lifetime: 服务生命周期
            factory: 工厂函数（可选）

        Returns:
            self，支持链式调用
        """
        impl = implementation or service_type

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=impl,
            lifetime=lifetime,
            factory=factory,
        )

        with self._lock:
            self._services[service_type] = descriptor
            # 如果实现类与服务类型不同，也注册实现类
            if impl != service_type and isinstance(impl, type):
                self._services[impl] = descriptor

        logger.debug(f"Service registered: {service_type.__name__} -> {impl}")
        return self

    def add_singleton(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
        factory: Callable[..., T] | None = None,
    ) -> "ServiceContainer":
        """添加单例服务"""
        return self.register(service_type, implementation, ServiceLifetime.SINGLETON, factory)

    def add_transient(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
        factory: Callable[..., T] | None = None,
    ) -> "ServiceContainer":
        """添加瞬态服务"""
        return self.register(service_type, implementation, ServiceLifetime.TRANSIENT, factory)

    def add_scoped(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
        factory: Callable[..., T] | None = None,
    ) -> "ServiceContainer":
        """添加作用域服务"""
        return self.register(service_type, implementation, ServiceLifetime.SCOPED, factory)

    def add_instance(self, service_type: type[T], instance: T) -> "ServiceContainer":
        """
        添加已存在的实例

        Args:
            service_type: 服务类型
            instance: 服务实例

        Returns:
            self，支持链式调用
        """
        with self._lock:
            self._instances[service_type] = instance
            # 同时注册到服务描述符
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation=instance,
                lifetime=ServiceLifetime.SINGLETON,
            )
            self._services[service_type] = descriptor

        logger.debug(f"Instance registered: {service_type.__name__}")
        return self

    def override(self, service_type: type[T], instance: T) -> "ServiceContainer":
        """
        覆盖服务实例（用于测试替身）

        Args:
            service_type: 服务类型
            instance: 替换实例

        Returns:
            self，支持链式调用
        """
        with self._lock:
            self._overrides[service_type] = instance

        logger.debug(f"Service overridden: {service_type.__name__}")
        return self

    def clear_override(self, service_type: type[T]) -> "ServiceContainer":
        """清除覆盖实例"""
        with self._lock:
            self._overrides.pop(service_type, None)

        logger.debug(f"Service override cleared: {service_type.__name__}")
        return self

    def clear_all_overrides(self) -> "ServiceContainer":
        """清除所有覆盖实例"""
        with self._lock:
            self._overrides.clear()

        logger.debug("All service overrides cleared")
        return self

    def get(self, service_type: type[T]) -> T:
        """
        获取服务实例

        Args:
            service_type: 服务类型

        Returns:
            服务实例

        Raises:
            KeyError: 服务未注册
        """
        # 1. 检查覆盖实例（测试替身）和缓存实例
        with self._lock:
            if service_type in self._overrides:
                return self._overrides[service_type]
            if service_type in self._instances:
                return self._instances[service_type]
            descriptor = self._services.get(service_type)
        if descriptor is None:
            raise KeyError(f"Service not registered: {service_type.__name__}")

        # 4. 根据生命周期创建实例
        return self._create_instance(descriptor, service_type)

    def _build_instance(self, descriptor: ServiceDescriptor) -> Any:
        if descriptor.factory:
            return descriptor.factory()
        if not isinstance(descriptor.implementation, type):
            return descriptor.implementation
        return descriptor.implementation()

    def _create_instance(self, descriptor: ServiceDescriptor, service_type: type[T]) -> T:
        """
        创建服务实例

        Args:
            descriptor: 服务描述符
            service_type: 服务类型

        Returns:
            服务实例
        """
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            with self._lock:
                if descriptor._instance is not None:
                    self._instances.setdefault(service_type, descriptor._instance)
                    return descriptor._instance
                instance = self._build_instance(descriptor)
                descriptor._instance = instance
                self._instances[service_type] = instance
                return instance

        return self._build_instance(descriptor)

    def try_get(self, service_type: type[T]) -> T | None:
        """
        尝试获取服务实例

        Args:
            service_type: 服务类型

        Returns:
            服务实例，如果未注册则返回 None
        """
        try:
            return self.get(service_type)
        except KeyError:
            return None

    def is_registered(self, service_type: type) -> bool:
        """检查服务是否已注册"""
        return service_type in self._services or service_type in self._instances

    async def start_services(self):
        """
        启动所有需要启动的服务

        调用服务的 start() 方法（如果存在）
        """
        if self._started:
            logger.warning("ServiceContainer already started")
            return

        logger.info("Starting services...")

        # 按依赖顺序启动服务
        startup_order = self._get_startup_order()

        for service_type in startup_order:
            try:
                instance = self.get(service_type)
                if hasattr(instance, "start") and callable(instance.start):
                    await instance.start()
                    logger.debug(f"Service started: {service_type.__name__}")
            except Exception as e:
                logger.error(f"Failed to start service {service_type.__name__}: {e}")
                raise

        self._started = True
        logger.info("All services started")

    async def stop_services(self):
        """
        停止所有服务

        调用服务的 stop() 方法（如果存在）
        """
        if self._stopped:
            logger.warning("ServiceContainer already stopped")
            return

        logger.info("Stopping services...")

        # 按相反顺序停止服务
        shutdown_order = list(reversed(self._get_startup_order()))

        for service_type in shutdown_order:
            try:
                instance = self.try_get(service_type)
                if instance and hasattr(instance, "stop") and callable(instance.stop):
                    await instance.stop()
                    logger.debug(f"Service stopped: {service_type.__name__}")
            except Exception as e:
                logger.error(f"Failed to stop service {service_type.__name__}: {e}")
                # 继续停止其他服务

        self._stopped = True
        logger.info("All services stopped")

    def _get_startup_order(self) -> list:
        """
        获取服务启动顺序

        Returns:
            服务类型列表（按启动顺序）
        """
        # 定义服务启动顺序（依赖关系）
        # 基础服务先启动，依赖服务后启动
        priority_order = [
            # 配置服务（最先）
            "ConfigService",
            # 统一缓存管理器（CacheManager）
            "CacheManager",
            # 缓存服务
            "CacheService",
            "CacheServiceUnified",
            "CacheServiceLegacy",
            "LinkCache",
            "LinkCacheUnified",
            "LinkCacheLegacy",
            # 定时任务服务
            "CronService",
            # 通知服务
            "NotificationService",
            # 其他服务
        ]

        ordered_services = []
        remaining_services = []

        for service_type in self._services.keys():
            service_name = service_type.__name__
            if service_name in priority_order:
                ordered_services.append((priority_order.index(service_name), service_type))
            else:
                remaining_services.append(service_type)

        # 按优先级排序
        ordered_services.sort(key=lambda x: x[0])
        result = [s[1] for s in ordered_services]

        # 添加剩余服务
        result.extend(remaining_services)

        return result

    def get_all_services(self) -> dict[type, Any]:
        """获取所有已注册的服务"""
        return {service_type: self.get(service_type) for service_type in self._services.keys()}

    def get_service_info(self) -> dict[str, Any]:
        """
        获取服务信息

        Returns:
            服务信息字典
        """
        return {
            "registered_services": [t.__name__ for t in self._services.keys()],
            "singleton_instances": [t.__name__ for t in self._instances.keys()],
            "overrides": [t.__name__ for t in self._overrides.keys()],
            "started": self._started,
            "stopped": self._stopped,
        }


# 全局服务容器实例
_global_container: ServiceContainer | None = None
_container_lock = threading.Lock()


def get_service_container() -> ServiceContainer:
    """
    获取全局服务容器实例

    Returns:
        ServiceContainer 实例
    """
    global _global_container

    if _global_container is None:
        with _container_lock:
            if _global_container is None:
                _global_container = ServiceContainer()

    return _global_container


def reset_service_container():
    """
    重置全局服务容器

    用于测试环境
    """
    global _global_container

    with _container_lock:
        _global_container = None

    logger.debug("Service container reset")
