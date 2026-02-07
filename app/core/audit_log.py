# -*- coding: utf-8 -*-
"""
审计日志模块

记录关键业务操作，便于问题追溯和合规审计

特性：
- 独立的审计日志文件
- 结构化日志格式（JSON）
- 支持关键操作记录（重命名、删除、配置变更等）
- 异步写入，不影响主流程性能
- 自动归档和清理
"""

import json
import asyncio
import aiofiles
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuditAction(Enum):
    """审计操作类型"""
    # 文件操作
    FILE_RENAME = "file_rename"           # 文件重命名
    FILE_DELETE = "file_delete"           # 文件删除
    FILE_MOVE = "file_move"               # 文件移动
    FILE_COPY = "file_copy"               # 文件复制
    
    # 批量操作
    BATCH_RENAME = "batch_rename"         # 批量重命名
    BATCH_DELETE = "batch_delete"         # 批量删除
    BATCH_SCRAPE = "batch_scrape"         # 批量刮削
    
    # 配置变更
    CONFIG_UPDATE = "config_update"       # 配置更新
    CONFIG_DELETE = "config_delete"       # 配置删除
    
    # 网盘操作
    CLOUD_UPLOAD = "cloud_upload"         # 上传到网盘
    CLOUD_DOWNLOAD = "cloud_download"     # 从网盘下载
    CLOUD_DELETE = "cloud_delete"         # 删除网盘文件
    
    # 任务操作
    TASK_CREATE = "task_create"           # 创建任务
    TASK_CANCEL = "task_cancel"           # 取消任务
    TASK_RETRY = "task_retry"             # 重试任务
    
    # 用户操作
    USER_LOGIN = "user_login"             # 用户登录
    USER_LOGOUT = "user_logout"           # 用户登出
    USER_UPDATE = "user_update"           # 用户信息更新
    
    # 系统操作
    SYSTEM_START = "system_start"         # 系统启动
    SYSTEM_STOP = "system_stop"           # 系统停止
    BACKUP_CREATE = "backup_create"       # 创建备份
    BACKUP_RESTORE = "backup_restore"     # 恢复备份


class AuditLevel(Enum):
    """审计级别"""
    INFO = "info"         # 普通信息
    IMPORTANT = "important"  # 重要操作
    CRITICAL = "critical"    # 关键操作


@dataclass
class AuditRecord:
    """审计记录数据结构"""
    timestamp: str                    # ISO格式时间戳
    action: str                       # 操作类型
    level: str                        # 审计级别
    user_id: Optional[str]            # 用户ID
    user_name: Optional[str]          # 用户名
    ip_address: Optional[str]         # IP地址
    request_id: Optional[str]         # 请求ID
    
    # 操作详情
    resource_type: Optional[str]      # 资源类型（file/config/task等）
    resource_id: Optional[str]        # 资源ID
    resource_name: Optional[str]      # 资源名称
    
    # 变更内容
    before_value: Optional[Any]       # 变更前的值
    after_value: Optional[Any]        # 变更后的值
    
    # 操作结果
    status: str                       # 状态: success/failure
    error_message: Optional[str]      # 错误信息
    
    # 额外信息
    metadata: Optional[Dict]          # 元数据
    duration_ms: Optional[int]        # 操作耗时（毫秒）
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class AuditLogger:
    """
    审计日志记录器
    
    专门用于记录关键业务操作，与常规日志分离
    """
    
    def __init__(
        self,
        log_dir: str = "logs/audit",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_files: int = 30,  # 保留30个文件
        async_queue_size: int = 1000
    ):
        """
        初始化审计日志记录器
        
        Args:
            log_dir: 日志目录
            max_file_size: 单个文件最大大小
            max_files: 保留文件数量
            async_queue_size: 异步队列大小
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_file_size = max_file_size
        self.max_files = max_files
        
        # 当前日志文件
        self.current_file: Optional[Path] = None
        self.current_size = 0
        
        # 异步队列
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=async_queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # 初始化当前文件
        self._init_current_file()
        
        logger.info(f"AuditLogger initialized: log_dir={log_dir}")
    
    def _init_current_file(self):
        """初始化当前日志文件"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.current_file = self.log_dir / f"audit_{today}.log"
        
        # 如果文件存在，获取当前大小
        if self.current_file.exists():
            self.current_size = self.current_file.stat().st_size
        else:
            self.current_size = 0
    
    async def start(self):
        """启动审计日志服务"""
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("AuditLogger started")
    
    async def stop(self):
        """停止审计日志服务"""
        # 等待队列处理完成
        await self._queue.join()
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("AuditLogger stopped")
    
    async def _worker(self):
        """后台写入工作线程"""
        while True:
            try:
                record = await self._queue.get()
                await self._write_record(record)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audit log worker error: {e}")
    
    async def _write_record(self, record: AuditRecord):
        """写入单条记录"""
        async with self._lock:
            try:
                # 检查是否需要轮转
                await self._rotate_if_needed()
                
                # 写入记录
                line = record.to_json() + "\n"
                async with aiofiles.open(self.current_file, "a", encoding="utf-8") as f:
                    await f.write(line)
                
                self.current_size += len(line.encode("utf-8"))
                
            except Exception as e:
                logger.error(f"Failed to write audit record: {e}")
    
    async def _rotate_if_needed(self):
        """检查并执行日志轮转"""
        if self.current_size >= self.max_file_size:
            # 创建新文件
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            new_file = self.log_dir / f"audit_{timestamp}.log"
            self.current_file = new_file
            self.current_size = 0
            
            # 清理旧文件
            await self._cleanup_old_files()
    
    async def _cleanup_old_files(self):
        """清理旧日志文件"""
        try:
            log_files = sorted(
                self.log_dir.glob("audit_*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # 删除超出保留数量的文件
            for old_file in log_files[self.max_files:]:
                old_file.unlink()
                logger.debug(f"Removed old audit log: {old_file}")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}")
    
    async def log(
        self,
        action: AuditAction,
        level: AuditLevel = AuditLevel.INFO,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        before_value: Optional[Any] = None,
        after_value: Optional[Any] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None,
        duration_ms: Optional[int] = None
    ):
        """
        记录审计日志
        
        Args:
            action: 操作类型
            level: 审计级别
            user_id: 用户ID
            user_name: 用户名
            ip_address: IP地址
            request_id: 请求ID
            resource_type: 资源类型
            resource_id: 资源ID
            resource_name: 资源名称
            before_value: 变更前值
            after_value: 变更后值
            status: 状态 (success/failure)
            error_message: 错误信息
            metadata: 元数据
            duration_ms: 操作耗时（毫秒）
        """
        record = AuditRecord(
            timestamp=datetime.now().isoformat(),
            action=action.value,
            level=level.value,
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            request_id=request_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            before_value=before_value,
            after_value=after_value,
            status=status,
            error_message=error_message,
            metadata=metadata,
            duration_ms=duration_ms
        )
        
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            # 队列满时同步写入
            await self._write_record(record)
    
    # ==================== 便捷方法 ====================
    
    async def log_rename(
        self,
        old_name: str,
        new_name: str,
        resource_type: str = "file",
        **kwargs
    ):
        """记录重命名操作"""
        await self.log(
            action=AuditAction.FILE_RENAME,
            level=AuditLevel.IMPORTANT,
            resource_type=resource_type,
            resource_name=f"{old_name} -> {new_name}",
            before_value=old_name,
            after_value=new_name,
            **kwargs
        )
    
    async def log_batch_rename(
        self,
        files: List[Dict[str, str]],  # [{"old": "x", "new": "y"}]
        success_count: int,
        failure_count: int,
        **kwargs
    ):
        """记录批量重命名操作"""
        await self.log(
            action=AuditAction.BATCH_RENAME,
            level=AuditLevel.CRITICAL,
            resource_type="batch",
            resource_name=f"批量重命名 {len(files)} 个文件",
            status="success" if failure_count == 0 else "partial" if success_count > 0 else "failure",
            metadata={
                "total_count": len(files),
                "success_count": success_count,
                "failure_count": failure_count,
                "files": files[:10]  # 只记录前10个
            },
            **kwargs
        )
    
    async def log_delete(
        self,
        resource_name: str,
        resource_type: str = "file",
        **kwargs
    ):
        """记录删除操作"""
        await self.log(
            action=AuditAction.FILE_DELETE,
            level=AuditLevel.IMPORTANT,
            resource_type=resource_type,
            resource_name=resource_name,
            **kwargs
        )
    
    async def log_config_update(
        self,
        config_key: str,
        old_value: Any,
        new_value: Any,
        **kwargs
    ):
        """记录配置变更"""
        # 敏感信息脱敏
        def mask_sensitive(value):
            if isinstance(value, str) and any(k in config_key.lower() for k in ["password", "token", "secret", "cookie", "key"]):
                return "***masked***"
            return value
        
        await self.log(
            action=AuditAction.CONFIG_UPDATE,
            level=AuditLevel.IMPORTANT,
            resource_type="config",
            resource_id=config_key,
            before_value=mask_sensitive(old_value),
            after_value=mask_sensitive(new_value),
            **kwargs
        )
    
    async def log_task(
        self,
        task_action: AuditAction,
        task_id: str,
        task_name: str,
        status: str = "success",
        **kwargs
    ):
        """记录任务操作"""
        await self.log(
            action=task_action,
            level=AuditLevel.INFO,
            resource_type="task",
            resource_id=task_id,
            resource_name=task_name,
            status=status,
            **kwargs
        )
    
    async def log_cloud_operation(
        self,
        action: AuditAction,
        cloud_type: str,  # quark/115/etc
        file_name: str,
        file_id: Optional[str] = None,
        **kwargs
    ):
        """记录网盘操作"""
        await self.log(
            action=action,
            level=AuditLevel.IMPORTANT,
            resource_type=f"cloud:{cloud_type}",
            resource_id=file_id,
            resource_name=file_name,
            **kwargs
        )


# 全局实例
_global_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志记录器"""
    global _global_audit_logger
    
    if _global_audit_logger is None:
        _global_audit_logger = AuditLogger()
    
    return _global_audit_logger


# 装饰器：自动记录函数调用

def audit_log(
    action: AuditAction,
    level: AuditLevel = AuditLevel.INFO,
    resource_type: Optional[str] = None,
    get_resource_name: Optional[callable] = None
):
    """
    审计日志装饰器
    
    自动记录函数调用和结果
    
    Args:
        action: 操作类型
        level: 审计级别
        resource_type: 资源类型
        get_resource_name: 从函数参数获取资源名称的函数
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            audit = get_audit_logger()
            
            # 获取资源名称
            resource_name = None
            if get_resource_name:
                try:
                    resource_name = get_resource_name(*args, **kwargs)
                except:
                    pass
            
            start_time = datetime.now()
            
            try:
                result = await func(*args, **kwargs)
                
                # 记录成功
                duration = int((datetime.now() - start_time).total_seconds() * 1000)
                await audit.log(
                    action=action,
                    level=level,
                    resource_type=resource_type,
                    resource_name=resource_name,
                    status="success",
                    duration_ms=duration
                )
                
                return result
                
            except Exception as e:
                # 记录失败
                duration = int((datetime.now() - start_time).total_seconds() * 1000)
                await audit.log(
                    action=action,
                    level=level,
                    resource_type=resource_type,
                    resource_name=resource_name,
                    status="failure",
                    error_message=str(e),
                    duration_ms=duration
                )
                raise
        
        return wrapper
    return decorator
