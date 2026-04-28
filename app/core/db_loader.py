"""
数据库预加载策略

提供 SQLAlchemy 查询优化，使用 selectinload/joinedload 避免 N+1 查询问题。
"""

from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload, subqueryload

from app.core.logging import get_logger


logger = get_logger(__name__)

ModelType = TypeVar("ModelType")
LoadOption = Any  # SQLAlchemy 加载选项类型


class QueryOptimizer:
    """
    查询优化器

    提供统一的预加载策略配置，避免 N+1 查询问题。

    用法:
        # 在 service 层使用
        from app.core.db_loader import QueryOptimizer

        optimizer = QueryOptimizer()

        # 获取预加载选项
        options = optimizer.get_user_options()

        # 执行查询
        stmt = select(User).options(*options)
        users = await session.execute(stmt)
    """

    @staticmethod
    def joinedload(*attrs: Any) -> LoadOption:
        """
        JOIN 预加载（适用于一对一/多对一关系）

        使用 SQL JOIN 一次性加载关联数据，适用于：
        - 一对一关系
        - 多对一关系
        - 关联数据量小的场景
        """
        return joinedload(*attrs)

    @staticmethod
    def selectinload(*attrs: Any) -> LoadOption:
        """
        SELECT IN 预加载（适用于一对多关系）

        使用 WHERE IN 查询加载关联数据，适用于：
        - 一对多关系
        - 多对多关系
        - 关联数据量大的场景
        """
        return selectinload(*attrs)

    @staticmethod
    def subqueryload(*attrs: Any) -> LoadOption:
        """
        子查询预加载（适用于复杂一对多关系）

        使用子查询加载关联数据，适用于：
        - 需要进一步过滤的关联数据
        - 复杂的一对多关系
        """
        return subqueryload(*attrs)

    # ==================== 模型特定的预加载策略 ====================

    @staticmethod
    def get_user_options() -> list[LoadOption]:
        """
        用户模型预加载选项

        预加载：
        - security_events (一对多，使用 selectinload)
        """
        from app.models.user import User

        return [
            selectinload(User.security_events),
        ]

    @staticmethod
    def get_scrape_options() -> list[LoadOption]:
        """
        刮削记录模型预加载选项

        预加载：
        - 相关文件记录
        """

        return [
            # 根据实际模型关系调整
        ]

    @staticmethod
    def get_task_options() -> list[LoadOption]:
        """
        任务模型预加载选项

        预加载：
        - 任务关联的用户（多对一，使用 joinedload）
        """

        return [
            # 根据实际模型关系调整
            # joinedload(Task.user),
        ]

    @staticmethod
    def get_emby_options() -> list[LoadOption]:
        """
        Emby 相关模型预加载选项
        """

        return [
            # 根据实际模型关系调整
        ]

    @staticmethod
    def get_notification_options() -> list[LoadOption]:
        """
        通知模型预加载选项
        """

        return [
            # 根据实际模型关系调整
        ]

    @staticmethod
    def apply_options(stmt, model_type: str) -> Any:
        """
        应用预加载选项到查询语句

        Args:
            stmt: SQLAlchemy 查询语句
            model_type: 模型类型 ('user', 'task', 'scrape', 'emby', 'notification')

        Returns:
            应用了预加载选项的查询语句
        """
        options_map = {
            "user": QueryOptimizer.get_user_options,
            "task": QueryOptimizer.get_task_options,
            "scrape": QueryOptimizer.get_scrape_options,
            "emby": QueryOptimizer.get_emby_options,
            "notification": QueryOptimizer.get_notification_options,
        }

        get_options = options_map.get(model_type)
        if not get_options:
            logger.warning(f"Unknown model type: {model_type}")
            return stmt

        return stmt.options(*get_options())


# ==================== 辅助函数 ====================


def optimize_query(stmt, model_type: str) -> Any:
    """
    便捷函数：应用预加载优化到查询

    Args:
        stmt: SQLAlchemy 查询语句
        model_type: 模型类型

    Returns:
        优化后的查询语句
    """
    return QueryOptimizer.apply_options(stmt, model_type)


def create_optimized_select(model_type: str, *filter_args, **filter_kwargs) -> Any:
    """
    便捷函数：创建优化的 SELECT 查询

    Args:
        model_type: 模型类型 ('user', 'task', 'scrape', 'emby', 'notification')
        *filter_args: 过滤条件
        **filter_kwargs: 命名过滤条件

    Returns:
        优化后的查询语句
    """
    from app.models.emby import EmbyCache
    from app.models.notification import Notification
    from app.models.scrape import ScrapeRecord
    from app.models.task import Task
    from app.models.user import User

    model_map = {
        "user": User,
        "task": Task,
        "scrape": ScrapeRecord,
        "emby": EmbyCache,
        "notification": Notification,
    }

    model = model_map.get(model_type)
    if not model:
        raise ValueError(f"Unknown model type: {model_type}")

    stmt = select(model).filter_by(**filter_kwargs) if filter_kwargs else select(model)
    return optimize_query(stmt, model_type)


# ==================== 使用示例 ====================
"""
# 示例 1: 手动应用预加载
from app.core.db_loader import QueryOptimizer

async def get_user_with_events(session, user_id: int):
    options = QueryOptimizer.get_user_options()
    stmt = select(User).options(*options).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar()

# 示例 2: 使用便捷函数
from app.core.db_loader import create_optimized_select

async def get_active_users(session):
    stmt = create_optimized_select("user", is_active=True)
    result = await session.execute(stmt)
    return result.scalars().all()

# 示例 3: 在 service 层使用
from app.core.db_loader import optimize_query

class UserService:
    async def get_users(self, session):
        stmt = select(User)
        stmt = optimize_query(stmt, "user")
        result = await session.execute(stmt)
        return result.scalars().all()
"""
