"""
安全审计服务

提供安全事件记录、分析和告警功能
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.security_event import (
    IPAccessRecord,
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventStatus,
    SecurityEventType,
)


logger = get_logger(__name__)


class SecurityAuditService:
    """
    安全审计服务

    功能：
    - 记录安全事件
    - 检测异常访问模式
    - 触发安全告警
    - 提供安全事件查询
    """

    _instance = None

    def __init__(self):
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "SecurityAuditService":
        """获取单例实例"""
        if not cls._instance:
            cls._instance = SecurityAuditService()
        return cls._instance

    async def initialize(self) -> None:
        """初始化服务"""
        if self._initialized:
            return
        self._initialized = True
        logger.info("SecurityAuditService initialized")

    # ==================== 事件记录方法 ====================

    def record_login_failed(
        self,
        db: Session,
        username: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        failure_reason: str | None = None,
        request_path: str = "/api/auth/login",
    ) -> SecurityEvent:
        """
        记录登录失败事件

        Args:
            db: 数据库会话
            username: 用户名
            ip_address: IP 地址
            user_agent: User-Agent
            failure_reason: 失败原因
            request_path: 请求路径

        Returns:
            SecurityEvent 实例
        """
        # 记录 IP 访问
        if ip_address:
            IPAccessRecord.record_access(
                db=db,
                ip_address=ip_address,
                access_type="login",
                success=False,
                username=username,
                user_agent=user_agent,
            )

        # 检查是否触发告警阈值
        severity = SecurityEventSeverity.LOW
        should_notify = False

        # 统计最近失败次数
        recent_failures = SecurityEvent.count_by_type(
            db=db,
            event_type=SecurityEventType.LOGIN_FAILED,
            minutes=15,
            ip_address=ip_address,
            username=username,
        )

        # 根据失败次数调整严重级别
        if recent_failures >= 5:
            severity = SecurityEventSeverity.HIGH
            should_notify = True
        elif recent_failures >= 3:
            severity = SecurityEventSeverity.MEDIUM

        # 创建事件
        event = SecurityEvent.create(
            db=db,
            event_type=SecurityEventType.LOGIN_FAILED,
            title=f"登录失败: {username}",
            severity=severity,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            description=f"用户 {username} 登录失败，原因: {failure_reason or '未知'}",
            details={
                "failure_reason": failure_reason,
                "recent_failures": recent_failures,
            },
            request_path=request_path,
            request_method="POST",
        )

        # 触发告警通知
        if should_notify:
            self._schedule_security_alert(event)

        return event

    def record_login_success(
        self,
        db: Session,
        user_id: int,
        username: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SecurityEvent:
        """
        记录登录成功事件

        Args:
            db: 数据库会话
            user_id: 用户 ID
            username: 用户名
            ip_address: IP 地址
            user_agent: User-Agent

        Returns:
            SecurityEvent 实例
        """
        # 记录 IP 访问
        if ip_address:
            IPAccessRecord.record_access(
                db=db,
                ip_address=ip_address,
                access_type="login",
                success=True,
                user_id=user_id,
                username=username,
                user_agent=user_agent,
            )

        # 检查是否为异常 IP（从未登录过的 IP）
        is_new_ip = self._check_new_ip(db, user_id, ip_address)

        severity = SecurityEventSeverity.LOW
        if is_new_ip:
            severity = SecurityEventSeverity.MEDIUM

        return SecurityEvent.create(
            db=db,
            event_type=SecurityEventType.LOGIN_SUCCESS,
            title=f"登录成功: {username}",
            severity=severity,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            description=f"用户 {username} 登录成功",
            details={"is_new_ip": is_new_ip},
            request_path="/api/auth/login",
            request_method="POST",
        )

    def record_account_locked(
        self,
        db: Session,
        user_id: int,
        username: str,
        ip_address: str | None = None,
        lock_duration_minutes: int = 15,
    ) -> SecurityEvent:
        """
        记录账户锁定事件

        Args:
            db: 数据库会话
            user_id: 用户 ID
            username: 用户名
            ip_address: IP 地址
            lock_duration_minutes: 锁定时长

        Returns:
            SecurityEvent 实例
        """
        event = SecurityEvent.create(
            db=db,
            event_type=SecurityEventType.ACCOUNT_LOCKED,
            title=f"账户锁定: {username}",
            severity=SecurityEventSeverity.HIGH,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"用户 {username} 账户已锁定 {lock_duration_minutes} 分钟",
            details={"lock_duration_minutes": lock_duration_minutes},
        )

        # 发送告警通知
        asyncio.create_task(self._send_security_alert(event))

        return event

    def record_unauthorized_access(
        self,
        db: Session,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_path: str | None = None,
        request_method: str | None = None,
        user_id: int | None = None,
        username: str | None = None,
    ) -> SecurityEvent:
        """
        记录未授权访问尝试

        Args:
            db: 数据库会话
            ip_address: IP 地址
            user_agent: User-Agent
            request_path: 请求路径
            request_method: 请求方法
            user_id: 用户 ID
            username: 用户名

        Returns:
            SecurityEvent 实例
        """
        # 记录 IP 访问
        if ip_address:
            IPAccessRecord.record_access(
                db=db,
                ip_address=ip_address,
                access_type="api",
                success=False,
                user_id=user_id,
                username=username,
                user_agent=user_agent,
            )

        # 检查是否为暴力破解
        recent_attempts = SecurityEvent.count_by_type(
            db=db,
            event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
            minutes=5,
            ip_address=ip_address,
        )

        severity = SecurityEventSeverity.MEDIUM
        if recent_attempts >= 10:
            severity = SecurityEventSeverity.HIGH

        return SecurityEvent.create(
            db=db,
            event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
            title="未授权访问尝试",
            severity=severity,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            description="检测到未授权访问尝试",
            details={"recent_attempts": recent_attempts},
            request_path=request_path,
            request_method=request_method,
        )

    def record_sensitive_config_change(
        self,
        db: Session,
        user_id: int,
        username: str,
        config_key: str,
        old_value: str | None = None,
        new_value: str | None = None,
        ip_address: str | None = None,
    ) -> SecurityEvent:
        """
        记录敏感配置变更

        Args:
            db: 数据库会话
            user_id: 用户 ID
            username: 用户名
            config_key: 配置键
            old_value: 旧值
            new_value: 新值
            ip_address: IP 地址

        Returns:
            SecurityEvent 实例
        """
        event = SecurityEvent.create(
            db=db,
            event_type=SecurityEventType.SENSITIVE_CONFIG_CHANGE,
            title=f"敏感配置变更: {config_key}",
            severity=SecurityEventSeverity.HIGH,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"用户 {username} 修改了敏感配置 {config_key}",
            details={
                "config_key": config_key,
                "old_value": "***" if old_value else None,
                "new_value": "***" if new_value else None,
            },
        )

        # 发送告警通知
        self._schedule_security_alert(event)

        return event

    def record_api_key_changed(
        self,
        db: Session,
        user_id: int,
        username: str,
        ip_address: str | None = None,
    ) -> SecurityEvent:
        """
        记录 API 密钥变更

        Args:
            db: 数据库会话
            user_id: 用户 ID
            username: 用户名
            ip_address: IP 地址

        Returns:
            SecurityEvent 实例
        """
        event = SecurityEvent.create(
            db=db,
            event_type=SecurityEventType.API_KEY_CHANGED,
            title="API 密钥变更",
            severity=SecurityEventSeverity.HIGH,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            description=f"用户 {username} 修改了 API 密钥",
        )

        # 发送告警通知
        self._schedule_security_alert(event)

        return event

    def record_injection_attempt(
        self,
        db: Session,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_path: str | None = None,
        request_method: str | None = None,
        injection_type: str = "unknown",
        payload: str | None = None,
    ) -> SecurityEvent:
        """
        记录注入攻击尝试

        Args:
            db: 数据库会话
            ip_address: IP 地址
            user_agent: User-Agent
            request_path: 请求路径
            request_method: 请求方法
            injection_type: 注入类型 (sql/xss/command/etc)
            payload: 攻击载荷

        Returns:
            SecurityEvent 实例
        """
        event = SecurityEvent.create(
            db=db,
            event_type=SecurityEventType.INJECTION_ATTEMPT,
            title=f"注入攻击尝试: {injection_type}",
            severity=SecurityEventSeverity.HIGH,
            ip_address=ip_address,
            user_agent=user_agent,
            description=f"检测到 {injection_type} 注入攻击尝试",
            details={
                "injection_type": injection_type,
                "payload": payload[:500] if payload else None,  # 限制长度
            },
            request_path=request_path,
            request_method=request_method,
        )

        # 发送告警通知
        self._schedule_security_alert(event)

        return event

    # ==================== 检测方法 ====================

    def detect_injection_attempt(self, input_string: str) -> str | None:
        """
        检测输入字符串中是否包含注入攻击特征

        Args:
            input_string: 输入字符串

        Returns:
            检测到的注入类型，或 None
        """
        if not input_string:
            return None

        # SQL 注入特征
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
            r"(--|#|/\*|\*/)",
            r"(\bOR\b|\bAND\b)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+",
            r"(\bunion\b.*\bselect\b)",
            r"(\bexec\b|\bexecute\b)",
        ]

        # XSS 特征
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe",
            r"<object",
            r"<embed",
        ]

        # 命令注入特征
        command_patterns = [
            r"[;&|`$]",
            r"\b(cat|ls|pwd|whoami|id|uname|wget|curl)\b",
            r"\.\./",
            r"\|\s*\w+",
        ]

        # 检测 SQL 注入
        for pattern in sql_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return "sql"

        # 检测 XSS
        for pattern in xss_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return "xss"

        # 检测命令注入
        for pattern in command_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return "command"

        return None

    def check_brute_force(
        self,
        db: Session,
        ip_address: str,
        minutes: int = 15,
        threshold: int = 10,
    ) -> bool:
        """
        检查是否为暴力破解

        Args:
            db: 数据库会话
            ip_address: IP 地址
            minutes: 时间窗口
            threshold: 阈值

        Returns:
            是否为暴力破解
        """
        failed_logins = SecurityEvent.count_by_type(
            db=db,
            event_type=SecurityEventType.LOGIN_FAILED,
            minutes=minutes,
            ip_address=ip_address,
        )

        return failed_logins >= threshold

    def _check_new_ip(self, db: Session, user_id: int, ip_address: str | None) -> bool:
        """
        检查是否为新 IP

        Args:
            db: 数据库会话
            user_id: 用户 ID
            ip_address: IP 地址

        Returns:
            是否为新 IP
        """
        if not ip_address:
            return False

        # 查找该用户之前是否从这个 IP 登录过
        existing = (
            db.query(SecurityEvent)
            .filter(
                SecurityEvent.user_id == user_id,
                SecurityEvent.event_type == SecurityEventType.LOGIN_SUCCESS.value,
                SecurityEvent.ip_address == ip_address,
            )
            .first()
        )

        return existing is None

    # ==================== 告警方法 ====================

    def _schedule_security_alert(self, event: SecurityEvent) -> None:
        """
        调度安全告警通知（兼容同步和异步上下文）

        Args:
            event: 安全事件
        """
        try:
            # 尝试在现有事件循环中调度
            loop = asyncio.get_running_loop()
            loop.create_task(self._send_security_alert(event))
        except RuntimeError:
            # 没有运行的事件循环，在新线程中运行
            import threading

            thread = threading.Thread(target=self._run_alert_in_thread, args=(event,), daemon=True)
            thread.start()

    def _run_alert_in_thread(self, event: SecurityEvent) -> None:
        """
        在新线程中运行告警

        Args:
            event: 安全事件
        """
        try:
            asyncio.run(self._send_security_alert(event))
        except Exception as e:
            logger.error(f"Failed to send security alert in thread: {e}")

    async def _send_security_alert(self, event: SecurityEvent) -> None:
        """
        发送安全告警通知

        Args:
            event: 安全事件
        """
        try:
            from app.services.notification_service import (
                NotificationPriority,
                NotificationType,
                get_notification_service,
            )

            notification_service = get_notification_service()

            # 确定通知优先级
            priority_map = {
                SecurityEventSeverity.LOW: NotificationPriority.LOW,
                SecurityEventSeverity.MEDIUM: NotificationPriority.NORMAL,
                SecurityEventSeverity.HIGH: NotificationPriority.HIGH,
                SecurityEventSeverity.CRITICAL: NotificationPriority.HIGH,
            }

            priority = priority_map.get(SecurityEventSeverity(event.severity), NotificationPriority.NORMAL)

            # 构建通知内容
            title = f"🚨 安全告警: {event.title}"
            content = f"""
事件类型: {event.event_type}
严重级别: {event.severity}
用户: {event.username or "未知"}
IP 地址: {event.ip_address or "未知"}
时间: {event.created_at.strftime("%Y-%m-%d %H:%M:%S") if event.created_at else "未知"}
描述: {event.description or "无"}
            """.strip()

            await notification_service.send_notification(
                type=NotificationType.SYSTEM_ALERT,
                title=title,
                content=content,
                priority=priority,
                metadata={
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "ip_address": event.ip_address,
                    "username": event.username,
                },
            )

            logger.info(f"Security alert sent for event {event.id}")

        except Exception as e:
            logger.error(f"Failed to send security alert: {e}")

    # ==================== 查询方法 ====================

    def get_security_events(
        self,
        db: Session,
        limit: int = 100,
        event_type: SecurityEventType | None = None,
        severity: SecurityEventSeverity | None = None,
        status: SecurityEventStatus | None = None,
        user_id: int | None = None,
        ip_address: str | None = None,
    ) -> list[SecurityEvent]:
        """
        获取安全事件列表

        Args:
            db: 数据库会话
            limit: 返回数量限制
            event_type: 过滤事件类型
            severity: 过滤严重级别
            status: 过滤状态
            user_id: 过滤用户 ID
            ip_address: 过滤 IP 地址

        Returns:
            SecurityEvent 列表
        """
        return SecurityEvent.get_recent(
            db=db,
            limit=limit,
            event_type=event_type,
            severity=severity,
            status=status,
            user_id=user_id,
            ip_address=ip_address,
        )

    def get_security_summary(
        self,
        db: Session,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        获取安全事件摘要

        Args:
            db: 数据库会话
            days: 统计天数

        Returns:
            摘要数据
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # 统计各类型事件数量
        events = db.query(SecurityEvent).filter(SecurityEvent.created_at >= cutoff).all()

        type_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}

        for event in events:
            type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
            severity_counts[event.severity] = severity_counts.get(event.severity, 0) + 1
            status_counts[event.status] = status_counts.get(event.status, 0) + 1

        # 获取可疑 IP
        suspicious_ips = IPAccessRecord.get_suspicious_ips(db, limit=10)

        return {
            "total_events": len(events),
            "by_type": type_counts,
            "by_severity": severity_counts,
            "by_status": status_counts,
            "suspicious_ips": [ip.to_dict() for ip in suspicious_ips],
            "period_days": days,
        }

    def acknowledge_event(
        self,
        db: Session,
        event_id: int,
        user_id: int,
        note: str | None = None,
    ) -> SecurityEvent | None:
        """
        确认安全事件

        Args:
            db: 数据库会话
            event_id: 事件 ID
            user_id: 用户 ID
            note: 备注

        Returns:
            更新后的事件
        """
        event = SecurityEvent.get_by_id(db, event_id)
        if event:
            event.acknowledge(db, user_id, note)
        return event

    def resolve_event(
        self,
        db: Session,
        event_id: int,
        user_id: int,
        note: str | None = None,
    ) -> SecurityEvent | None:
        """
        解决安全事件

        Args:
            db: 数据库会话
            event_id: 事件 ID
            user_id: 用户 ID
            note: 备注

        Returns:
            更新后的事件
        """
        event = SecurityEvent.get_by_id(db, event_id)
        if event:
            event.resolve(db, user_id, note)
        return event


def get_security_audit_service() -> SecurityAuditService:
    """获取安全审计服务实例"""
    return SecurityAuditService.get_instance()
