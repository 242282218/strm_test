"""
认证服务

提供用户认证、JWT 令牌管理和密码处理功能
"""

import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.env_aliases import JWT_SECRET_KEY_ENV_PRIORITY, get_env_override
from app.core.logging import get_logger
from app.models.user import LoginAttempt, User


logger = get_logger(__name__)

# JWT 配置
JWT_SECRET_KEY = get_env_override(*JWT_SECRET_KEY_ENV_PRIORITY)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_HOURS", "1"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def get_access_token_max_age_seconds() -> int:
    """Return the JWT access-token lifetime in seconds."""
    return JWT_ACCESS_TOKEN_EXPIRE_HOURS * 60 * 60


def generate_bootstrap_password() -> str:
    """Generate a one-time bootstrap password for first-run admin setup."""
    return secrets.token_urlsafe(18)


# 登录限流配置
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOCK_DURATION_MINUTES = int(os.getenv("LOCK_DURATION_MINUTES", "15"))


def _get_jwt_secret_key() -> str:
    """
    获取 JWT 密钥

    优先从 canonical 环境变量读取，否则使用 legacy alias 或配置文件。
    生产环境强制要求配置 JWT secret。
    """
    global JWT_SECRET_KEY
    if not JWT_SECRET_KEY:
        JWT_SECRET_KEY = get_env_override(*JWT_SECRET_KEY_ENV_PRIORITY)
        env = os.getenv("ENVIRONMENT", "development")

        if not JWT_SECRET_KEY:
            # 尝试从配置服务读取
            try:
                from app.services.config_service import get_config_service

                config = get_config_service().get_config()
                if hasattr(config, "security") and hasattr(config.security, "jwt_secret_key"):
                    JWT_SECRET_KEY = config.security.jwt_secret_key
            except Exception as e:
                logger.warning(f"Failed to load JWT secret from config: {e}")

        # 如果仍然没有，检查环境并处理
        if not JWT_SECRET_KEY:
            if env == "production":
                raise RuntimeError(
                    "JWT secret must be configured in production environment. "
                    "Set SMART_MEDIA_JWT_SECRET_KEY or configure security.jwt_secret_key in config.yaml."
                )

            JWT_SECRET_KEY = secrets.token_urlsafe(32)
            logger.warning(
                "JWT secret not configured. Using generated random key (development only). "
                "Set SMART_MEDIA_JWT_SECRET_KEY for production."
            )

    return JWT_SECRET_KEY


class AuthService:
    """
    认证服务类

    提供完整的用户认证功能：
    - 密码哈希和验证
    - JWT 令牌生成和验证
    - 登录限流
    - 用户管理
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """
        使用 bcrypt 哈希密码

        Args:
            password: 明文密码

        Returns:
            哈希后的密码
        """
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        验证密码

        Args:
            plain_password: 明文密码
            hashed_password: 哈希密码

        Returns:
            是否匹配
        """
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    @staticmethod
    def create_access_token(
        user_id: int,
        username: str,
        role: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        创建 JWT 访问令牌

        Args:
            user_id: 用户 ID
            username: 用户名
            role: 用户角色
            expires_delta: 过期时间增量

        Returns:
            JWT 令牌
        """
        if expires_delta is None:
            expires_delta = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)

        now = datetime.utcnow()
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": expire,
        }

        token = jwt.encode(payload, _get_jwt_secret_key(), algorithm=JWT_ALGORITHM)
        logger.debug(f"Created access token for user {username}, expires at {expire}")
        return token

    @staticmethod
    def create_refresh_token(
        user_id: int,
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        创建刷新令牌

        Args:
            user_id: 用户 ID
            expires_delta: 过期时间增量

        Returns:
            刷新令牌
        """
        if expires_delta is None:
            expires_delta = timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        now = datetime.utcnow()
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "iat": now,
            "exp": expire,
        }

        token = jwt.encode(payload, _get_jwt_secret_key(), algorithm=JWT_ALGORITHM)
        logger.debug(f"Created refresh token for user {user_id}, expires at {expire}")
        return token

    @staticmethod
    def decode_token(token: str) -> dict | None:
        """
        解码并验证 JWT 令牌

        Args:
            token: JWT 令牌

        Returns:
            解码后的 payload 或 None
        """
        try:
            payload = jwt.decode(token, _get_jwt_secret_key(), algorithms=[JWT_ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            return None

    @staticmethod
    def verify_access_token(token: str) -> int | None:
        """
        验证访问令牌并返回用户 ID

        Args:
            token: JWT 访问令牌

        Returns:
            用户 ID 或 None
        """
        payload = AuthService.decode_token(token)
        if not payload:
            return None

        if payload.get("type") != "access":
            logger.warning("Token is not an access token")
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return int(user_id)

    @staticmethod
    def verify_refresh_token(token: str) -> int | None:
        """
        验证刷新令牌并返回用户 ID

        Args:
            token: 刷新令牌

        Returns:
            用户 ID 或 None
        """
        payload = AuthService.decode_token(token)
        if not payload:
            return None

        if payload.get("type") != "refresh":
            logger.warning("Token is not a refresh token")
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return int(user_id)

    @staticmethod
    def authenticate_user(
        db: Session,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User | None, str | None]:
        """
        认证用户

        Args:
            db: 数据库会话
            username: 用户名
            password: 密码
            ip_address: 客户端 IP
            user_agent: 客户端 User-Agent

        Returns:
            (用户对象, 错误消息) - 成功时错误消息为 None
        """
        # 导入安全审计服务
        from app.services.security_audit_service import get_security_audit_service

        security_audit = get_security_audit_service()

        # 查找用户
        user = User.get_by_username(db, username)

        if not user:
            # 记录失败尝试
            LoginAttempt.log_attempt(
                db=db,
                username=username,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="user_not_found",
            )
            # 记录安全事件
            security_audit.record_login_failed(
                db=db,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="user_not_found",
            )
            logger.warning(f"Login attempt with non-existent user: {username}")
            return None, "用户名或密码错误"

        # 检查账户是否激活
        if not user.is_active:
            LoginAttempt.log_attempt(
                db=db,
                username=username,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="account_disabled",
            )
            security_audit.record_login_failed(
                db=db,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="account_disabled",
            )
            logger.warning(f"Login attempt for disabled account: {username}")
            return None, "账户已被禁用"

        # 检查账户是否被锁定
        if user.is_locked():
            LoginAttempt.log_attempt(
                db=db,
                username=username,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="account_locked",
            )
            security_audit.record_login_failed(
                db=db,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="account_locked",
            )
            logger.warning(f"Login attempt for locked account: {username}")
            return None, "账户已被锁定，请稍后再试"

        # 验证密码
        if not AuthService.verify_password(password, user.password_hash):
            # 增加失败计数
            is_locked = user.increment_failed_login(
                db=db,
                max_attempts=MAX_LOGIN_ATTEMPTS,
                lock_duration_minutes=LOCK_DURATION_MINUTES,
            )

            LoginAttempt.log_attempt(
                db=db,
                username=username,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="invalid_password",
            )

            # 记录安全事件
            security_audit.record_login_failed(
                db=db,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="invalid_password",
            )

            # 如果账户被锁定，记录锁定事件
            if is_locked:
                security_audit.record_account_locked(
                    db=db,
                    user_id=user.id,
                    username=username,
                    ip_address=ip_address,
                    lock_duration_minutes=LOCK_DURATION_MINUTES,
                )
                return None, f"密码错误次数过多，账户已锁定 {LOCK_DURATION_MINUTES} 分钟"

            remaining = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
            return None, f"用户名或密码错误，剩余尝试次数: {remaining}"

        # 认证成功
        user.update_last_login(db)
        LoginAttempt.log_attempt(
            db=db,
            username=username,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        # 记录登录成功事件
        security_audit.record_login_success(
            db=db,
            user_id=user.id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(f"User authenticated successfully: {username}")
        return user, None

    @staticmethod
    def create_user(
        db: Session,
        username: str,
        password: str,
        email: str | None = None,
        role: str = "user",
    ) -> User:
        """
        创建新用户

        Args:
            db: 数据库会话
            username: 用户名
            password: 明文密码
            email: 邮箱
            role: 角色

        Returns:
            User 实例
        """
        # 检查用户名是否已存在
        existing = User.get_by_username(db, username)
        if existing:
            raise ValueError(f"用户名已存在: {username}")

        # 哈希密码
        password_hash = AuthService.hash_password(password)

        # 创建用户
        user = User.create(
            db=db,
            username=username,
            password_hash=password_hash,
            email=email,
            role=role,
        )

        logger.info(f"Created new user: {username} with role: {role}")
        return user

    @staticmethod
    def change_password(
        db: Session,
        user: User,
        old_password: str,
        new_password: str,
    ) -> bool:
        """
        修改密码

        Args:
            db: 数据库会话
            user: 用户对象
            old_password: 原密码
            new_password: 新密码

        Returns:
            是否成功
        """
        # 验证原密码
        if not AuthService.verify_password(old_password, user.password_hash):
            logger.warning(f"Password change failed - invalid old password for user: {user.username}")
            return False

        # 更新密码
        user.password_hash = AuthService.hash_password(new_password)
        db.commit()

        logger.info(f"Password changed for user: {user.username}")
        return True

    @staticmethod
    def init_default_admin(db: Session) -> User | None:
        """
        初始化默认管理员账户

        如果 admin 用户不存在，则创建默认管理员

        Args:
            db: 数据库会话

        Returns:
            创建的管理员用户或 None
        """
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD")
        if not admin_password:
            raise ValueError("ADMIN_PASSWORD must be configured before initializing the default admin")

        # 检查是否已存在
        existing = User.get_by_username(db, admin_username)
        if existing:
            logger.debug(f"Admin user already exists: {admin_username}")
            return None

        # 创建管理员
        admin = AuthService.create_user(
            db=db,
            username=admin_username,
            password=admin_password,
            role="admin",
        )

        logger.info(f"Created default admin user: {admin_username}")
        return admin


def get_auth_service() -> AuthService:
    """
    获取认证服务实例

    Returns:
        AuthService 实例
    """
    return AuthService()


def init_auth_system() -> None:
    """
    初始化认证系统

    创建默认管理员账户（如果不存在）
    """
    db = SessionLocal()
    try:
        AuthService.init_default_admin(db)
    except Exception as e:
        logger.error(f"Failed to initialize auth system: {e}")
    finally:
        db.close()
