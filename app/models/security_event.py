"""
安全事件模型

定义安全事件类型、严重级别和审计记录
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.logging import get_logger


logger = get_logger(__name__)


class SecurityEventType(str, Enum):
    """安全事件类型"""

    # 认证相关
    LOGIN_FAILED = "login_failed"  # 登录失败
    LOGIN_SUCCESS = "login_success"  # 登录成功
    ACCOUNT_LOCKED = "account_locked"  # 账户锁定
    ACCOUNT_UNLOCKED = "account_unlocked"  # 账户解锁

    # 异常访问
    ABNORMAL_IP_ACCESS = "abnormal_ip_access"  # 异常 IP 访问
    SUSPICIOUS_ACTIVITY = "suspicious_activity"  # 可疑活动
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"  # 暴力破解尝试

    # 权限相关
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # 未授权访问尝试
    PRIVILEGE_ESCALATION = "privilege_escalation"  # 权限提升尝试
    PERMISSION_DENIED = "permission_denied"  # 权限拒绝

    # 配置变更
    SENSITIVE_CONFIG_CHANGE = "sensitive_config_change"  # 敏感配置变更
    API_KEY_CHANGED = "api_key_changed"  # API 密钥变更
    USER_ROLE_CHANGED = "user_role_changed"  # 用户角色变更

    # 系统安全
    API_KEY_LEAKED = "api_key_leaked"  # API 密钥泄露检测
    INJECTION_ATTEMPT = "injection_attempt"  # 注入攻击尝试
    XSS_ATTEMPT = "xss_attempt"  # XSS 攻击尝试


class SecurityEventSeverity(str, Enum):
    """安全事件严重级别"""

    LOW = "low"  # 低风险 - 记录日志
    MEDIUM = "medium"  # 中风险 - 记录日志 + 可选通知
    HIGH = "high"  # 高风险 - 立即通知
    CRITICAL = "critical"  # 严重 - 立即通知 + 可能触发防护措施


class SecurityEventStatus(str, Enum):
    """安全事件状态"""

    NEW = "new"  # 新事件
    ACKNOWLEDGED = "acknowledged"  # 已确认
    RESOLVED = "resolved"  # 已解决
    FALSE_POSITIVE = "false_positive"  # 误报


# 告警规则配置
ALERT_RULES = {
    # 连续登录失败触发告警的阈值
    SecurityEventType.LOGIN_FAILED: {
        "threshold": 5,  # 连续失败次数
        "window_minutes": 15,  # 时间窗口
        "severity": SecurityEventSeverity.HIGH,
        "notify": True,
    },
    # 账户锁定
    SecurityEventType.ACCOUNT_LOCKED: {
        "severity": SecurityEventSeverity.HIGH,
        "notify": True,
    },
    # 异常 IP 访问
    SecurityEventType.ABNORMAL_IP_ACCESS: {
        "severity": SecurityEventSeverity.MEDIUM,
        "notify": True,
    },
    # 暴力破解
    SecurityEventType.BRUTE_FORCE_ATTEMPT: {
        "severity": SecurityEventSeverity.CRITICAL,
        "notify": True,
    },
    # 未授权访问
    SecurityEventType.UNAUTHORIZED_ACCESS: {
        "severity": SecurityEventSeverity.MEDIUM,
        "notify": True,
    },
    # 敏感配置变更
    SecurityEventType.SENSITIVE_CONFIG_CHANGE: {
        "severity": SecurityEventSeverity.HIGH,
        "notify": True,
    },
    # API 密钥泄露
    SecurityEventType.API_KEY_LEAKED: {
        "severity": SecurityEventSeverity.CRITICAL,
        "notify": True,
    },
    # 注入攻击
    SecurityEventType.INJECTION_ATTEMPT: {
        "severity": SecurityEventSeverity.HIGH,
        "notify": True,
    },
}


class SecurityEvent(Base):
    """
    安全事件模型

    记录所有安全相关事件，用于审计和告警
    """

    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, index=True, comment="事件类型")
    severity = Column(String(20), nullable=False, default=SecurityEventSeverity.LOW, comment="严重级别")
    status = Column(String(20), nullable=False, default=SecurityEventStatus.NEW, comment="事件状态")

    # 事件主体
    user_id = Column(Integer, nullable=True, index=True, comment="关联用户ID")
    username = Column(String(64), nullable=True, index=True, comment="用户名")
    ip_address = Column(String(45), nullable=True, index=True, comment="客户端IP地址")
    user_agent = Column(String(512), nullable=True, comment="客户端User-Agent")

    # 事件详情
    title = Column(String(200), nullable=False, comment="事件标题")
    description = Column(Text, nullable=True, comment="事件描述")
    details = Column(JSON, nullable=True, comment="详细信息(JSON)")

    # 请求上下文
    request_path = Column(String(500), nullable=True, comment="请求路径")
    request_method = Column(String(10), nullable=True, comment="请求方法")

    # 处理信息
    acknowledged_by = Column(Integer, nullable=True, comment="确认人ID")
    acknowledged_at = Column(DateTime, nullable=True, comment="确认时间")
    resolved_by = Column(Integer, nullable=True, comment="解决人ID")
    resolved_at = Column(DateTime, nullable=True, comment="解决时间")
    resolution_note = Column(Text, nullable=True, comment="解决说明")

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")

    # 索引
    __table_args__ = (
        Index("idx_security_events_type", "event_type"),
        Index("idx_security_events_severity", "severity"),
        Index("idx_security_events_status", "status"),
        Index("idx_security_events_created_at", "created_at"),
        Index("idx_security_events_user_id", "user_id"),
        Index("idx_security_events_ip_address", "ip_address"),
    )

    @classmethod
    def create(
        cls,
        db: Session,
        event_type: SecurityEventType,
        title: str,
        severity: SecurityEventSeverity = SecurityEventSeverity.LOW,
        user_id: int | None = None,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        description: str | None = None,
        details: dict | None = None,
        request_path: str | None = None,
        request_method: str | None = None,
    ) -> "SecurityEvent":
        """
        创建安全事件

        Args:
            db: 数据库会话
            event_type: 事件类型
            title: 事件标题
            severity: 严重级别
            user_id: 用户ID
            username: 用户名
            ip_address: IP地址
            user_agent: User-Agent
            description: 描述
            details: 详细信息
            request_path: 请求路径
            request_method: 请求方法

        Returns:
            SecurityEvent 实例
        """
        event = cls(
            event_type=event_type.value,
            severity=severity.value,
            title=title,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
            details=details,
            request_path=request_path,
            request_method=request_method,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        logger.info(
            f"Security event created: {event_type.value} - {title}",
            extra={
                "event_id": event.id,
                "event_type": event_type.value,
                "severity": severity.value,
                "username": username,
                "ip_address": ip_address,
            },
        )
        return event

    @classmethod
    def get_by_id(cls, db: Session, event_id: int) -> Optional["SecurityEvent"]:
        """根据ID获取事件"""
        return db.query(cls).filter(cls.id == event_id).first()

    @classmethod
    def get_recent(
        cls,
        db: Session,
        limit: int = 100,
        event_type: SecurityEventType | None = None,
        severity: SecurityEventSeverity | None = None,
        status: SecurityEventStatus | None = None,
        user_id: int | None = None,
        ip_address: str | None = None,
    ) -> list["SecurityEvent"]:
        """
        获取最近的安全事件

        Args:
            db: 数据库会话
            limit: 返回数量限制
            event_type: 过滤事件类型
            severity: 过滤严重级别
            status: 过滤状态
            user_id: 过滤用户ID
            ip_address: 过滤IP地址

        Returns:
            SecurityEvent 列表
        """
        query = db.query(cls)

        if event_type:
            query = query.filter(cls.event_type == event_type.value)
        if severity:
            query = query.filter(cls.severity == severity.value)
        if status:
            query = query.filter(cls.status == status.value)
        if user_id:
            query = query.filter(cls.user_id == user_id)
        if ip_address:
            query = query.filter(cls.ip_address == ip_address)

        return query.order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def count_by_type(
        cls,
        db: Session,
        event_type: SecurityEventType,
        minutes: int = 60,
        ip_address: str | None = None,
        username: str | None = None,
    ) -> int:
        """
        统计指定时间窗口内某类型事件的数量

        Args:
            db: 数据库会话
            event_type: 事件类型
            minutes: 时间窗口（分钟）
            ip_address: 过滤IP地址
            username: 过滤用户名

        Returns:
            事件数量
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        query = db.query(cls).filter(
            cls.event_type == event_type.value,
            cls.created_at >= cutoff,
        )

        if ip_address:
            query = query.filter(cls.ip_address == ip_address)
        if username:
            query = query.filter(cls.username == username)

        return query.count()

    def acknowledge(self, db: Session, user_id: int, note: str | None = None) -> None:
        """确认事件"""
        self.status = SecurityEventStatus.ACKNOWLEDGED.value
        self.acknowledged_by = user_id
        self.acknowledged_at = datetime.utcnow()
        if note:
            self.resolution_note = note
        db.commit()
        logger.info(f"Security event {self.id} acknowledged by user {user_id}")

    def resolve(self, db: Session, user_id: int, note: str | None = None) -> None:
        """解决事件"""
        self.status = SecurityEventStatus.RESOLVED.value
        self.resolved_by = user_id
        self.resolved_at = datetime.utcnow()
        if note:
            self.resolution_note = note
        db.commit()
        logger.info(f"Security event {self.id} resolved by user {user_id}")

    def mark_false_positive(self, db: Session, user_id: int, note: str | None = None) -> None:
        """标记为误报"""
        self.status = SecurityEventStatus.FALSE_POSITIVE.value
        self.resolved_by = user_id
        self.resolved_at = datetime.utcnow()
        if note:
            self.resolution_note = note
        db.commit()
        logger.info(f"Security event {self.id} marked as false positive by user {user_id}")

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "severity": self.severity,
            "status": self.status,
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "title": self.title,
            "description": self.description,
            "details": self.details,
            "request_path": self.request_path,
            "request_method": self.request_method,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<SecurityEvent(id={self.id}, type={self.event_type}, severity={self.severity})>"


class IPAccessRecord(Base):
    """
    IP 访问记录

    用于检测异常 IP 访问模式
    """

    __tablename__ = "ip_access_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(45), nullable=False, index=True, comment="IP地址")
    user_id = Column(Integer, nullable=True, index=True, comment="用户ID")
    username = Column(String(64), nullable=True, comment="用户名")
    access_type = Column(String(50), nullable=False, comment="访问类型(login/api/etc)")
    success = Column(Integer, default=0, nullable=False, comment="成功次数")
    failed = Column(Integer, default=0, nullable=False, comment="失败次数")
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False, comment="首次出现")
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False, comment="最后出现")
    user_agents = Column(JSON, nullable=True, comment="User-Agent列表")
    is_suspicious = Column(Integer, default=0, nullable=False, comment="是否可疑")
    country = Column(String(100), nullable=True, comment="国家")
    city = Column(String(100), nullable=True, comment="城市")

    __table_args__ = (
        Index("idx_ip_access_records_ip", "ip_address"),
        Index("idx_ip_access_records_user_id", "user_id"),
        Index("idx_ip_access_records_last_seen", "last_seen"),
    )

    @classmethod
    def record_access(
        cls,
        db: Session,
        ip_address: str,
        access_type: str,
        success: bool = True,
        user_id: int | None = None,
        username: str | None = None,
        user_agent: str | None = None,
    ) -> "IPAccessRecord":
        """
        记录 IP 访问

        Args:
            db: 数据库会话
            ip_address: IP 地址
            access_type: 访问类型
            success: 是否成功
            user_id: 用户 ID
            username: 用户名
            user_agent: User-Agent

        Returns:
            IPAccessRecord 实例
        """
        from datetime import datetime

        # 查找现有记录
        record = (
            db.query(cls)
            .filter(
                cls.ip_address == ip_address,
                cls.access_type == access_type,
            )
            .first()
        )

        now = datetime.utcnow()

        if record:
            # 更新现有记录
            if success:
                record.success += 1
            else:
                record.failed += 1
            record.last_seen = now
            record.user_id = user_id or record.user_id
            record.username = username or record.username

            # 更新 User-Agent 列表
            if user_agent:
                agents = record.user_agents or []
                if user_agent not in agents:
                    agents.append(user_agent)
                    record.user_agents = agents[-10:]  # 只保留最近10个

            # 检查是否可疑
            if record.failed > 10 or (record.failed > 5 and record.success == 0):
                record.is_suspicious = 1
        else:
            # 创建新记录
            record = cls(
                ip_address=ip_address,
                access_type=access_type,
                success=1 if success else 0,
                failed=0 if success else 1,
                user_id=user_id,
                username=username,
                user_agents=[user_agent] if user_agent else None,
            )
            db.add(record)

        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def get_suspicious_ips(cls, db: Session, limit: int = 100) -> list["IPAccessRecord"]:
        """获取可疑 IP 列表"""
        return db.query(cls).filter(cls.is_suspicious == 1).order_by(cls.last_seen.desc()).limit(limit).all()

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "ip_address": self.ip_address,
            "user_id": self.user_id,
            "username": self.username,
            "access_type": self.access_type,
            "success": self.success,
            "failed": self.failed,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_suspicious": bool(self.is_suspicious),
            "country": self.country,
            "city": self.city,
        }

    def __repr__(self) -> str:
        return f"<IPAccessRecord(ip={self.ip_address}, type={self.access_type})>"
