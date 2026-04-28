"""
认证模块测试

测试用户模型、认证服务和 API 端点
"""

import os
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models.user import LoginAttempt, User
from app.services.auth_service import AuthService


@pytest.fixture(scope="function")
def db():
    """创建测试数据库会话"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


class TestUserModel:
    """测试用户模型"""

    def test_create_user(self, db):
        """测试创建用户"""
        password_hash = AuthService.hash_password("test_password")
        user = User.create(
            db=db,
            username="testuser",
            password_hash=password_hash,
            email="test@example.com",
            role="user",
        )

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.is_active == True

    def test_get_by_username(self, db):
        """测试根据用户名获取用户"""
        password_hash = AuthService.hash_password("password123")
        User.create(
            db=db,
            username="findme",
            password_hash=password_hash,
        )

        user = User.get_by_username(db, "findme")
        assert user is not None
        assert user.username == "findme"

        # 测试不存在的用户
        not_found = User.get_by_username(db, "nonexistent")
        assert not_found is None

    def test_user_locking(self, db):
        """测试用户锁定机制"""
        password_hash = AuthService.hash_password("password123")
        user = User.create(
            db=db,
            username="lockme",
            password_hash=password_hash,
        )

        # 初始状态未锁定
        assert not user.is_locked()

        # 娡拟登录失败
        is_locked = user.increment_failed_login(db, max_attempts=5, lock_duration_minutes=15)
        assert not is_locked  # 第一次失败不锁定

        # 继续失败直到锁定
        for _ in range(4):
            is_locked = user.increment_failed_login(db, max_attempts=5, lock_duration_minutes=15)

        assert is_locked
        assert user.is_locked()

    def test_update_last_login(self, db):
        """测试更新最后登录时间"""
        password_hash = AuthService.hash_password("password123")
        user = User.create(
            db=db,
            username="loginuser",
            password_hash=password_hash,
        )

        original_login = user.last_login
        user.update_last_login(db)

        assert user.last_login is not None
        assert user.last_login != original_login
        assert user.failed_login_attempts == 0


class TestAuthService:
    """测试认证服务"""

    def test_hash_password(self):
        """测试密码哈希"""
        password = "my_secure_password"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert len(hashed) > 0
        assert AuthService.verify_password(password, hashed)

    def test_verify_password_invalid(self):
        """测试密码验证失败"""
        hashed = AuthService.hash_password("correct_password")
        assert not AuthService.verify_password("wrong_password", hashed)

    def test_create_access_token(self):
        """测试创建访问令牌"""
        token = AuthService.create_access_token(
            user_id=1,
            username="testuser",
            role="admin",
        )

        assert token is not None
        assert len(token) > 0

        # 验证令牌
        user_id = AuthService.verify_access_token(token)
        assert user_id == 1

    def test_create_refresh_token(self):
        """测试创建刷新令牌"""
        token = AuthService.create_refresh_token(user_id=1)

        assert token is not None
        assert len(token) > 0

        # 验证令牌
        user_id = AuthService.verify_refresh_token(token)
        assert user_id == 1

    def test_jwt_secret_key_can_be_loaded_from_security_config(self):
        """测试 JWT 密钥可从 security.jwt_secret_key 配置读取"""
        from types import SimpleNamespace

        from app.services import auth_service as auth_service_module

        original_secret = auth_service_module.JWT_SECRET_KEY
        auth_service_module.JWT_SECRET_KEY = ""
        try:
            config = SimpleNamespace(security=SimpleNamespace(jwt_secret_key="config-secret-key"))
            with patch("app.services.config_service.get_config_service") as mock_get_config_service:
                mock_get_config_service.return_value.get_config.return_value = config
                secret = auth_service_module._get_jwt_secret_key()

            assert secret == "config-secret-key"
        finally:
            auth_service_module.JWT_SECRET_KEY = original_secret

    def test_verify_expired_token(self):
        """测试过期令牌验证"""
        from datetime import timedelta

        # 创建一个立即过期的令牌
        token = AuthService.create_access_token(
            user_id=1,
            username="testuser",
            role="user",
            expires_delta=timedelta(seconds=-1),
        )

        # 验证过期令牌
        user_id = AuthService.verify_access_token(token)
        assert user_id is None

    def test_authenticate_user_success(self, db):
        """测试成功认证用户"""
        password = "correct_password"
        password_hash = AuthService.hash_password(password)
        User.create(
            db=db,
            username="authuser",
            password_hash=password_hash,
        )

        user, error = AuthService.authenticate_user(
            db=db,
            username="authuser",
            password=password,
        )

        assert user is not None
        assert error is None
        assert user.username == "authuser"

    def test_authenticate_user_wrong_password(self, db):
        """测试错误密码认证"""
        password_hash = AuthService.hash_password("correct_password")
        User.create(
            db=db,
            username="wrongpass",
            password_hash=password_hash,
        )

        user, error = AuthService.authenticate_user(
            db=db,
            username="wrongpass",
            password="wrong_password",
        )

        assert user is None
        assert error is not None
        assert "密码错误" in error or "用户名或密码错误" in error

    def test_authenticate_user_not_found(self, db):
        """测试用户不存在"""
        user, error = AuthService.authenticate_user(
            db=db,
            username="nonexistent",
            password="anypassword",
        )

        assert user is None
        assert error is not None

    def test_authenticate_user_locked(self, db):
        """测试锁定用户认证"""
        password_hash = AuthService.hash_password("password123")
        user = User.create(
            db=db,
            username="lockeduser",
            password_hash=password_hash,
        )

        # 锁定账户
        for _ in range(5):
            user.increment_failed_login(db, max_attempts=5, lock_duration_minutes=15)

        # 尝试认证
        user, error = AuthService.authenticate_user(
            db=db,
            username="lockeduser",
            password="password123",
        )

        assert user is None
        assert "锁定" in error or "locked" in error.lower()

    def test_create_user(self, db):
        """测试创建用户"""
        user = AuthService.create_user(
            db=db,
            username="newuser",
            password="newpassword",
            email="new@example.com",
            role="user",
        )

        assert user.id is not None
        assert user.username == "newuser"
        assert AuthService.verify_password("newpassword", user.password_hash)

    def test_create_duplicate_user(self, db):
        """测试创建重复用户"""
        AuthService.create_user(
            db=db,
            username="duplicate",
            password="password1",
        )

        with pytest.raises(ValueError, match="用户名已存在"):
            AuthService.create_user(
                db=db,
                username="duplicate",
                password="password2",
            )

    def test_init_default_admin_requires_explicit_password_configuration(self, db):
        """测试未配置环境变量时拒绝使用固定默认密码创建管理员"""
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match="ADMIN_PASSWORD"):
            AuthService.init_default_admin(db)

    def test_init_default_admin_prefers_env_password_when_configured(self, db):
        """测试已配置环境变量时优先使用环境变量密码"""
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "custom-admin-pass"}, clear=True):
            admin = AuthService.init_default_admin(db)

        assert admin is not None
        assert admin.username == "admin"
        authenticated_user, error = AuthService.authenticate_user(db, username="admin", password="custom-admin-pass")
        assert authenticated_user is not None
        assert error is None

    def test_change_password(self, db):
        """测试修改密码"""
        user = AuthService.create_user(
            db=db,
            username="changepass",
            password="oldpassword",
        )

        # 修改密码
        success = AuthService.change_password(
            db=db,
            user=user,
            old_password="oldpassword",
            new_password="newpassword",
        )

        assert success
        assert AuthService.verify_password("newpassword", user.password_hash)

    def test_change_password_wrong_old(self, db):
        """测试使用错误原密码修改"""
        user = AuthService.create_user(
            db=db,
            username="wrongoldpass",
            password="correctpassword",
        )

        success = AuthService.change_password(
            db=db,
            user=user,
            old_password="wrongpassword",
            new_password="newpassword",
        )

        assert not success


class TestLoginAttempt:
    """测试登录尝试记录"""

    def test_log_attempt(self, db):
        """测试记录登录尝试"""
        attempt = LoginAttempt.log_attempt(
            db=db,
            username="testuser",
            success=True,
            ip_address="192.168.1.1",
            user_agent="TestAgent",
        )

        assert attempt.id is not None
        assert attempt.username == "testuser"
        assert attempt.success == True
        assert attempt.ip_address == "192.168.1.1"

    def test_get_recent_failures(self, db):
        """测试获取最近失败次数"""
        # 记录一些失败
        LoginAttempt.log_attempt(db, "failuser", False, "192.168.1.1")
        LoginAttempt.log_attempt(db, "failuser", False, "192.168.1.1")
        LoginAttempt.log_attempt(db, "failuser", False, "192.168.1.1")

        # 获取失败次数
        count = LoginAttempt.get_recent_failures(db, "failuser", minutes=15)
        assert count == 3

        # 测试不存在的用户
        count = LoginAttempt.get_recent_failures(db, "nonexistent", minutes=15)
        assert count == 0
