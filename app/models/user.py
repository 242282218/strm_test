"""
用户模型

提供用户认证和授权功能
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.logging import get_logger


logger = get_logger(__name__)


class User(Base):
    """
    用户模型

    存储用户认证信息和账户状态
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(128), nullable=False, comment="密码哈希(bcrypt)")
    email = Column(String(128), nullable=True, unique=True, comment="邮箱地址")
    role = Column(String(32), default="user", nullable=False, comment="用户角色(admin/user)")
    is_active = Column(Boolean, default=True, nullable=False, comment="账户是否激活")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")
    last_login = Column(DateTime, nullable=True, comment="最后登录时间")
    failed_login_attempts = Column(Integer, default=0, nullable=False, comment="连续登录失败次数")
    locked_until = Column(DateTime, nullable=True, comment="账户锁定截止时间")

    # 添加索引
    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_email", "email"),
    )

    @classmethod
    def create(
        cls,
        db: Session,
        username: str,
        password_hash: str,
        email: str | None = None,
        role: str = "user",
    ) -> "User":
        """
        创建新用户

        Args:
            db: 数据库会话
            username: 用户名
            password_hash: 密码哈希
            email: 邮箱地址
            role: 用户角色

        Returns:
            User 实例
        """
        user = cls(
            username=username,
            password_hash=password_hash,
            email=email,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created user: {username}")
        return user

    @classmethod
    def get_by_username(cls, db: Session, username: str) -> Optional["User"]:
        """
        根据用户名获取用户

        Args:
            db: 数据库会话
            username: 用户名

        Returns:
            User 实例或 None
        """
        return db.query(cls).filter(cls.username == username).first()

    @classmethod
    def get_by_id(cls, db: Session, user_id: int) -> Optional["User"]:
        """
        根据 ID 获取用户

        Args:
            db: 数据库会话
            user_id: 用户 ID

        Returns:
            User 实例或 None
        """
        return db.query(cls).filter(cls.id == user_id).first()

    @classmethod
    def get_all_active(cls, db: Session) -> list["User"]:
        """
        获取所有活跃用户

        Args:
            db: 数据库会话

        Returns:
            User 列表
        """
        return db.query(cls).filter(cls.is_active == True).all()

    @classmethod
    def has_admin(cls, db: Session) -> bool:
        """Check whether any admin user exists."""
        return db.query(cls.id).filter(cls.role == "admin").first() is not None

    def update_last_login(self, db: Session) -> None:
        """
        更新最后登录时间并重置失败计数
        """
        self.last_login = datetime.utcnow()
        self.failed_login_attempts = 0
        self.locked_until = None
        db.commit()
        logger.debug(f"Updated last login for user: {self.username}")

    def increment_failed_login(self, db: Session, max_attempts: int = 5, lock_duration_minutes: int = 15) -> bool:
        """
        增加登录失败计数，超过阈值则锁定账户

        Args:
            db: 数据库会话
            max_attempts: 最大允许失败次数
            lock_duration_minutes: 锁定时长（分钟）

        Returns:
            是否已锁定
        """
        self.failed_login_attempts += 1

        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lock_duration_minutes)
            logger.warning(f"User {self.username} locked until {self.locked_until}")
            db.commit()
            return True

        db.commit()
        return False

    def is_locked(self) -> bool:
        """
        检查账户是否被锁定

        Returns:
            是否被锁定
        """
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def unlock(self, db: Session) -> None:
        """
        解锁账户
        """
        self.failed_login_attempts = 0
        self.locked_until = None
        db.commit()
        logger.info(f"Unlocked user: {self.username}")

    def to_dict(self) -> dict:
        """
        转换为字典格式

        Returns:
            字典格式的用户数据（不包含敏感信息）
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username!r}, role={self.role!r})>"


class LoginAttempt(Base):
    """
    登录尝试记录

    用于审计和安全分析
    """

    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, index=True, comment="尝试登录的用户名")
    ip_address = Column(String(45), nullable=True, comment="客户端 IP 地址")
    user_agent = Column(String(512), nullable=True, comment="客户端 User-Agent")
    success = Column(Boolean, default=False, nullable=False, comment="是否成功")
    failure_reason = Column(String(128), nullable=True, comment="失败原因")
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="尝试时间")

    __table_args__ = (
        Index("idx_login_attempts_username", "username"),
        Index("idx_login_attempts_attempted_at", "attempted_at"),
    )

    @classmethod
    def log_attempt(
        cls,
        db: Session,
        username: str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        failure_reason: str | None = None,
    ) -> "LoginAttempt":
        """
        记录登录尝试

        Args:
            db: 数据库会话
            username: 用户名
            success: 是否成功
            ip_address: IP 地址
            user_agent: User-Agent
            failure_reason: 失败原因

        Returns:
            LoginAttempt 实例
        """
        attempt = cls(
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason,
        )
        db.add(attempt)
        db.commit()
        return attempt

    @classmethod
    def get_recent_failures(cls, db: Session, username: str, minutes: int = 15) -> int:
        """
        获取最近 N 分钟内的失败次数

        Args:
            db: 数据库会话
            username: 用户名
            minutes: 时间范围（分钟）

        Returns:
            失败次数
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return (
            db.query(cls)
            .filter(
                cls.username == username,
                cls.success == False,
                cls.attempted_at >= cutoff,
            )
            .count()
        )

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "username": self.username,
            "ip_address": self.ip_address,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "attempted_at": self.attempted_at.isoformat() if self.attempted_at else None,
        }

    def __repr__(self) -> str:
        return f"<LoginAttempt(username={self.username!r}, success={self.success})>"
