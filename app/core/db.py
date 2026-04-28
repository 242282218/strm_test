"""
SQLAlchemy 数据库配置模块

提供连接池、会话管理和模型基类

重构改进:
    - 可配置的连接池参数
    - 连接池状态监控
    - 连接健康检查
    - 支持多种连接池策略
"""

import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, StaticPool

from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class PoolConfig:
    """连接池配置"""

    # 连接池大小（仅 QueuePool 有效）
    pool_size: int = 5
    # 最大溢出连接数（仅 QueuePool 有效）
    max_overflow: int = 10
    # 连接回收时间（秒），防止连接过期
    pool_recycle: int = 3600
    # 连接健康检查
    pool_pre_ping: bool = True
    # 连接超时时间（秒）
    pool_timeout: int = 30
    # SQLite 连接超时
    connect_timeout: int = 30


# 全局连接池配置实例
_pool_config = PoolConfig()


def configure_pool(
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_recycle: int = 3600,
    pool_pre_ping: bool = True,
    pool_timeout: int = 30,
    connect_timeout: int = 30,
) -> None:
    """
    配置连接池参数

    注意：需要在创建 engine 之前调用，或重新初始化数据库

    Args:
        pool_size: 连接池大小
        max_overflow: 最大溢出连接数
        pool_recycle: 连接回收时间（秒）
        pool_pre_ping: 是否启用连接健康检查
        pool_timeout: 连接池超时时间（秒）
        connect_timeout: 数据库连接超时（秒）
    """
    global _pool_config
    _pool_config = PoolConfig(
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
        pool_timeout=pool_timeout,
        connect_timeout=connect_timeout,
    )
    logger.info(f"Pool configuration updated: {_pool_config}")


def get_pool_config() -> PoolConfig:
    """获取当前连接池配置"""
    return _pool_config


def resolve_db_path(db_path: str | None = None) -> str:
    """
    解析数据库路径

    Args:
        db_path: 数据库路径（可选）

    Returns:
        解析后的绝对路径

    说明:
        - 如果未提供路径，从配置读取
        - 相对路径会解析到 data 目录
    """
    # 延迟导入避免循环依赖
    from app.services.config_service import get_config_service

    if not db_path:
        config = get_config_service().get_config()
        db_path = config.database
    path = Path(db_path).expanduser()
    if path.is_absolute():
        return str(path.resolve())
    return str(path.resolve())


def _build_sqlalchemy_url() -> str:
    """构建SQLAlchemy连接URL"""
    db_path = resolve_db_path()
    normalized = db_path.replace("\\", "/")
    return f"sqlite:///{normalized}"


def _get_sqlalchemy_url() -> str:
    global SQLALCHEMY_DATABASE_URL
    if not SQLALCHEMY_DATABASE_URL:
        SQLALCHEMY_DATABASE_URL = _build_sqlalchemy_url()
    return SQLALCHEMY_DATABASE_URL


SQLALCHEMY_DATABASE_URL: str | None = None
_engine_pool_class: type = StaticPool
_engine_lock = threading.RLock()


def _create_engine_with_pool(pool_class: type = StaticPool) -> Engine:
    """
    创建数据库引擎（带连接池配置）

    Args:
        pool_class: 连接池类型
            - StaticPool: 单连接模式（SQLite 默认）
            - QueuePool: 连接池模式（支持并发）
            - NullPool: 无连接池（每次创建新连接）

    Returns:
        SQLAlchemy Engine 实例
    """
    config = get_pool_config()

    # SQLite 特定配置
    sqlite_connect_args = {
        "check_same_thread": False,  # 允许多线程访问
        "timeout": config.connect_timeout,
    }

    database_url = _get_sqlalchemy_url()
    _ensure_sqlite_parent_dir(database_url)

    if pool_class == StaticPool:
        # StaticPool: 单连接模式，适合低并发场景
        engine = create_engine(
            database_url,
            connect_args=sqlite_connect_args,
            poolclass=StaticPool,
            echo=False,
        )
    elif pool_class == QueuePool:
        # QueuePool: 连接池模式，适合高并发场景
        engine = create_engine(
            database_url,
            connect_args=sqlite_connect_args,
            poolclass=QueuePool,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_recycle=config.pool_recycle,
            pool_pre_ping=config.pool_pre_ping,
            pool_timeout=config.pool_timeout,
            echo=False,
        )
    elif pool_class == NullPool:
        # NullPool: 无连接池，每次创建新连接
        engine = create_engine(
            database_url,
            connect_args=sqlite_connect_args,
            poolclass=NullPool,
            echo=False,
        )
    else:
        raise ValueError(f"Unsupported pool class: {pool_class}")

    return engine


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """Ensure file-based SQLite URLs have an existing parent directory."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return
    if not url.database or url.database == ":memory:":
        return
    Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


# 默认使用 StaticPool（SQLite 推荐配置）
# 如需切换到 QueuePool，修改此处为 QueuePool
engine: Engine | None = None


def get_engine() -> Engine:
    """获取数据库引擎，按需初始化。"""
    global engine
    with _engine_lock:
        database_url = _get_sqlalchemy_url()
        if engine is not None and str(engine.url) != database_url:
            engine.dispose()
            engine = None
        if engine is None:
            engine = _create_engine_with_pool(_engine_pool_class)
            _register_engine_events(engine)
        return engine


def reinitialize_engine(pool_class: type = StaticPool) -> Engine:
    """
    重新初始化数据库引擎

    用于在运行时切换连接池类型或更新配置

    Args:
        pool_class: 连接池类型

    Returns:
        新的 Engine 实例
    """
    global engine, SessionLocal, _engine_pool_class, SQLALCHEMY_DATABASE_URL

    with _engine_lock:
        old_engine = engine
        if old_engine is not None:
            old_engine.dispose()

        _engine_pool_class = pool_class
        SQLALCHEMY_DATABASE_URL = None
        engine = _create_engine_with_pool(pool_class)
        _register_engine_events(engine)
        SessionLocal.configure(bind=engine)

    logger.info(f"Database engine reinitialized with pool: {pool_class.__name__}")
    return engine


def _register_engine_events(target_engine: Engine) -> None:
    """注册引擎事件监听器"""

    # 延迟导入避免循环依赖
    from app.core.db_monitor import get_pool_monitor

    @event.listens_for(target_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """
        设置 SQLite PRAGMA 配置

        性能优化说明:
        - foreign_keys=ON: 启用外键约束，保证数据完整性
        - journal_mode=WAL: Write-Ahead Logging，提升并发读写性能
        - synchronous=NORMAL: 平衡性能与数据安全性
        - cache_size=-64000: 64MB 页缓存（负值表示 KB）
        - temp_store=MEMORY: 临时表存储在内存中
        - busy_timeout=30000: 30秒锁等待超时，减少 SQLITE_BUSY 错误
        - mmap_size=268435456: 256MB 内存映射 I/O，加速大文件读取
        - locking_mode=NORMAL: 允许多进程访问（WAL 模式下）
        """
        cursor = dbapi_conn.cursor()

        # 核心配置
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")

        # 性能优化配置
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB 缓存
        cursor.execute("PRAGMA temp_store=MEMORY")  # 临时表在内存中
        cursor.execute("PRAGMA busy_timeout=30000")  # 30秒锁等待
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        cursor.execute("PRAGMA locking_mode=NORMAL")  # 多进程访问

        # WAL 模式优化
        cursor.execute("PRAGMA wal_autocheckpoint=1000")  # 每1000页自动checkpoint

        cursor.close()
        logger.debug("SQLite PRAGMA configured for performance optimization")

    @event.listens_for(target_engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """连接检出事件 - 追踪连接使用"""
        conn_id = id(dbapi_connection)
        try:
            monitor = get_pool_monitor()
            monitor._tracker.on_connection_created(conn_id, "engine_checkout")
        except Exception as e:
            logger.debug(f"Failed to track connection checkout: {e}")
        logger.debug(f"Connection checkout: {conn_id}")

    @event.listens_for(target_engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """连接归还事件 - 追踪连接释放"""
        conn_id = id(dbapi_connection)
        try:
            monitor = get_pool_monitor()
            monitor._tracker.on_connection_closed(conn_id)
        except Exception as e:
            logger.debug(f"Failed to track connection checkin: {e}")
        logger.debug(f"Connection checkin: {conn_id}")


class LazySessionFactory:
    """按需绑定引擎的 Session 工厂。"""

    def __init__(self):
        self._factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,  # 提交后对象不过期
        )

    def configure(self, **kwargs):
        return self._factory.configure(**kwargs)

    def __call__(self, *args, **kwargs):
        active_engine = get_engine()
        if self._factory.kw.get("bind") is not active_engine:
            self._factory.configure(bind=active_engine)
        return self._factory(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._factory, name)


# 配置会话工厂
SessionLocal = LazySessionFactory()

# 声明基类
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    依赖注入获取数据库会话

    Yields:
        Session: SQLAlchemy 会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    上下文管理器获取数据库会话

    用于非 FastAPI 场景的手动会话管理

    Yields:
        Session: SQLAlchemy 会话对象

    Example:
        with get_db_session() as db:
            record = db.query(StrmRecord).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()


def get_pool_status() -> dict[str, Any]:
    """
    获取连接池状态

    Returns:
        连接池状态信息字典
    """
    active_engine = get_engine()
    pool = active_engine.pool

    status = {
        "pool_type": type(pool).__name__,
        "database_url": SQLALCHEMY_DATABASE_URL.split("/")[-1],  # 只显示文件名
    }

    # StaticPool 状态
    if isinstance(pool, StaticPool):
        status.update(
            {
                "mode": "single_connection",
                "description": "单连接模式，适合低并发场景",
            }
        )

    # QueuePool 状态
    elif hasattr(pool, "size"):
        status.update(
            {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalidatedcount() if hasattr(pool, "invalidatedcount") else 0,
                "mode": "connection_pool",
                "description": "连接池模式，支持高并发",
            }
        )

    # NullPool 状态
    elif type(pool).__name__ == "NullPool":
        status.update(
            {
                "mode": "no_pool",
                "description": "无连接池，每次创建新连接",
            }
        )

    return status


def check_pool_health() -> dict[str, Any]:
    """
    检查连接池健康状态

    Returns:
        健康检查结果
    """
    try:
        # 尝试执行简单查询
        with get_db_session() as db:
            db.execute(text("SELECT 1"))

        pool_status = get_pool_status()

        return {
            "healthy": True,
            "message": "Database connection pool is healthy",
            "pool_status": pool_status,
        }
    except Exception as e:
        logger.error(f"Pool health check failed: {e}")
        return {
            "healthy": False,
            "message": f"Database connection pool health check failed: {e!s}",
            "pool_status": get_pool_status(),
        }


def init_db():
    """
    初始化数据库表结构

    导入所有模型后调用此方法创建表并推进 schema version
    """
    from app.migrations.runner import run_migrations

    result = run_migrations(get_engine())
    logger.info(
        f"Database schema ready: version={result.current_version} "
        f"target={result.target_version} applied={list(result.applied_versions)}"
    )
    return result


def drop_all_tables():
    """
    删除所有表（仅用于测试）
    """
    Base.metadata.drop_all(bind=get_engine())
    logger.warning("All database tables dropped")
