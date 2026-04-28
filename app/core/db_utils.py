"""
数据库查询优化工具模块

提供批量查询、连接预加载等优化功能，消除N+1查询问题
"""

import asyncio
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Query, Session, joinedload, selectinload

from app.core.logging import get_logger


logger = get_logger(__name__)


class BatchQueryHelper:
    """批量查询助手类"""

    @staticmethod
    def batch_get_by_ids(
        session: Session, model_class: type[Any], ids: list[int], batch_size: int = 1000, id_field: str = "id"
    ) -> dict[int, Any]:
        """
        批量根据ID获取记录，避免N+1查询

        Args:
            session: 数据库会话
            model_class: 模型类
            ids: ID列表
            batch_size: 批次大小
            id_field: ID字段名

        Returns:
            {id: record} 字典
        """
        if not ids:
            return {}

        result = {}

        # 分批查询
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]

            # 构建查询
            query = session.query(model_class).filter(getattr(model_class, id_field).in_(batch_ids))

            # 执行查询
            batch_results = query.all()

            # 构建结果字典
            for record in batch_results:
                record_id = getattr(record, id_field)
                result[record_id] = record

        logger.debug(f"Batch query completed: {len(result)} records fetched for {len(ids)} IDs")
        return result

    @staticmethod
    def batch_get_by_field(
        session: Session, model_class: type[Any], field_name: str, values: list[Any], batch_size: int = 1000
    ) -> dict[Any, list[Any]]:
        """
        批量根据字段值获取记录

        Args:
            session: 数据库会话
            model_class: 模型类
            field_name: 字段名
            values: 字段值列表
            batch_size: 批次大小

        Returns:
            {field_value: [records]} 字典
        """
        if not values:
            return {}

        result = {}
        field_attr = getattr(model_class, field_name)

        # 初始化结果字典
        for value in values:
            result[value] = []

        # 分批查询
        for i in range(0, len(values), batch_size):
            batch_values = values[i : i + batch_size]

            # 构建查询
            query = session.query(model_class).filter(field_attr.in_(batch_values))

            # 执行查询
            batch_results = query.all()

            # 分组结果
            for record in batch_results:
                field_value = getattr(record, field_name)
                result[field_value].append(record)

        logger.debug(f"Batch field query completed: {sum(len(v) for v in result.values())} records fetched")
        return result


class QueryOptimizer:
    """查询优化器"""

    @staticmethod
    def apply_eager_loading(query: Query, relationships: list[str]) -> Query:
        """
        应用急切加载优化关联查询

        Args:
            query: SQLAlchemy查询对象
            relationships: 关联关系列表

        Returns:
            优化后的查询对象
        """
        for rel in relationships:
            # 根据关系类型选择合适的加载策略
            if "." in rel:
                # 嵌套关系使用joinedload
                query = query.options(joinedload(rel))
            else:
                # 简单关系使用selectinload
                query = query.options(selectinload(rel))

        return query

    @staticmethod
    def paginate_query(query: Query, page: int, page_size: int) -> Query:
        """
        为查询应用分页

        Args:
            query: SQLAlchemy查询对象
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            分页后的查询对象
        """
        offset = (page - 1) * page_size
        return query.offset(offset).limit(page_size)

    @staticmethod
    def add_performance_hints(query: Query) -> Query:
        """
        为查询添加性能优化提示

        Args:
            query: SQLAlchemy查询对象

        Returns:
            优化后的查询对象
        """
        # 添加索引提示（如果需要）
        # 注意：具体的hint语法取决于数据库类型
        return query


class AsyncBatchProcessor:
    """异步批处理处理器"""

    def __init__(self, batch_size: int = 100, delay: float = 0.01):
        """
        初始化批处理器

        Args:
            batch_size: 批次大小
            delay: 批次间延迟（秒）
        """
        self.batch_size = batch_size
        self.delay = delay
        self.semaphore = asyncio.Semaphore(10)  # 限制并发批次数量

    async def process_items_batched(self, items: list[Any], processor_func: Callable, *args, **kwargs) -> list[Any]:
        """
        分批异步处理项目列表

        Args:
            items: 待处理项目列表
            processor_func: 处理函数（可以是异步的）
            *args: 传递给处理函数的位置参数
            **kwargs: 传递给处理函数的关键字参数

        Returns:
            处理结果列表
        """
        if not items:
            return []

        results = []

        # 分批处理
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]

            async with self.semaphore:
                try:
                    if asyncio.iscoroutinefunction(processor_func):
                        batch_result = await processor_func(batch, *args, **kwargs)
                    else:
                        # 在线程池中执行同步函数
                        loop = asyncio.get_event_loop()
                        batch_result = await loop.run_in_executor(None, processor_func, batch, *args, **kwargs)

                    if isinstance(batch_result, list):
                        results.extend(batch_result)
                    else:
                        results.append(batch_result)

                except Exception as e:
                    logger.error(f"Batch processing failed for items {i}-{i + len(batch) - 1}: {e}")
                    # 可以选择继续处理其他批次或抛出异常
                    raise

                # 批次间短暂延迟
                if self.delay > 0:
                    await asyncio.sleep(self.delay)

                # 显式清理批次引用帮助GC
                del batch

        return results


class MemoryEfficientScanner:
    """内存高效扫描器"""

    @staticmethod
    async def scan_directory_streaming(
        directory_path: str,
        file_filter: Callable[[str], bool] | None = None,
        batch_processor: AsyncBatchProcessor | None = None,
    ):
        """
        流式扫描目录，避免一次性加载所有文件到内存

        Args:
            directory_path: 目录路径
            file_filter: 文件过滤函数
            batch_processor: 批处理器（可选）

        Returns:
            文件路径列表（使用批处理器时）或异步生成器（流式处理时）
        """
        import os

        def file_generator():
            """生成器函数，逐个产生文件路径"""
            try:
                for root, dirs, files in os.walk(directory_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if file_filter is None or file_filter(file_path):
                            yield file_path
            except Exception as e:
                logger.error(f"Error scanning directory {directory_path}: {e}")
                return

        if batch_processor:
            # 使用批处理器
            file_list = list(file_generator())
            return await batch_processor.process_items_batched(
                file_list,
                lambda batch: batch,  # 简单返回批次
            )
        # 返回文件列表（简化处理）
        return list(file_generator())


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.query_stats = {"total_queries": 0, "batch_queries": 0, "single_queries": 0, "avg_query_time": 0.0}
        self.memory_stats = {"peak_memory_mb": 0.0, "avg_memory_mb": 0.0}

    def record_query(self, query_time: float, is_batch: bool = False):
        """记录查询性能"""
        self.query_stats["total_queries"] += 1
        if is_batch:
            self.query_stats["batch_queries"] += 1
        else:
            self.query_stats["single_queries"] += 1

        # 更新平均查询时间
        total_time = self.query_stats["avg_query_time"] * (self.query_stats["total_queries"] - 1)
        self.query_stats["avg_query_time"] = (total_time + query_time) / self.query_stats["total_queries"]

    def get_stats(self) -> dict[str, Any]:
        """获取性能统计"""
        return {"query_stats": self.query_stats.copy(), "memory_stats": self.memory_stats.copy()}


# 全局性能监控器实例
_global_perf_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    return _global_perf_monitor


# 便捷函数
def batch_get_models_by_ids(session: Session, model_class: type[Any], ids: list[int]) -> dict[int, Any]:
    """便捷函数：批量获取模型记录"""
    return BatchQueryHelper.batch_get_by_ids(session, model_class, ids)


def optimize_query_with_relationships(query: Query, relationships: list[str]) -> Query:
    """便捷函数：优化查询关联加载"""
    return QueryOptimizer.apply_eager_loading(query, relationships)


async def process_items_in_batches(items: list[Any], processor_func: Callable, batch_size: int = 100) -> list[Any]:
    """便捷函数：分批处理项目"""
    processor = AsyncBatchProcessor(batch_size=batch_size)
    return await processor.process_items_batched(items, processor_func)
