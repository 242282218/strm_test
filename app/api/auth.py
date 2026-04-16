"""
认证 API 端点

提供 API Key 验证和用户认证功能
"""

import os
import secrets

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.core.auth_contract import resolve_expected_api_key
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.schemas.auth import ChangePasswordRequest, RefreshTokenRequest, TokenResponse
from app.services.auth_service import AuthService, get_access_token_max_age_seconds
from app.services.config_service import get_config_service


logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Cookie 配置
AUTH_COOKIE_NAME = "auth_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 天


class LoginRequest(BaseModel):
    """登录请求"""

    username: str | None = Field(None, description="Username for authentication")
    password: str | None = Field(None, description="Password for authentication")
    api_key: str | None = Field(None, description="API Key for authentication")


class UserResponse(BaseModel):
    """用户信息响应"""

    id: int
    username: str
    email: str | None = None
    role: str
    is_active: bool
    created_at: str | None = None
    last_login: str | None = None


class LoginResponse(BaseModel):
    """登录响应"""

    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int = Field(default_factory=get_access_token_max_age_seconds)
    user: UserResponse | None = None


class VerifyResponse(BaseModel):
    """验证响应"""

    valid: bool = Field(..., description="Whether the token is valid")
    message: str = Field(..., description="Status message")


class LogoutResponse(BaseModel):
    """登出响应"""

    success: bool = Field(..., description="Whether logout was successful")
    message: str = Field(..., description="Status message")


class InitAdminResponse(BaseModel):
    """初始化管理员响应"""

    success: bool = Field(..., description="Whether initialization was successful")
    message: str = Field(..., description="Status message")
    username: str = Field(..., description="Admin username")
    password_generated: bool = Field(False, description="Whether the bootstrap password was generated dynamically")
    generated_password: str | None = Field(None, description="Bootstrap password returned to the client")


def _get_expected_api_key() -> str | None:
    """
    获取配置的 API Key

    Priority:
    1. SMART_MEDIA_SECURITY_API_KEY environment variable
    2. SMART_MEDIA_API_KEY / API_KEY legacy environment aliases
    3. Config file security.api_key

    Returns:
        The expected API key or None if not configured
    """
    return resolve_expected_api_key(_get_config_api_key)


def _get_config_api_key() -> str | None:
    """Read configured API key from config service."""
    try:
        cfg = get_config_service().get_config()
        security = getattr(cfg, "security", None)
        if security and security.api_key:
            return security.api_key
    except Exception as exc:
        logger.warning(f"Failed to read API key from config: {exc}")

    return None


def _is_auth_required() -> bool:
    """
    检查是否需要认证

    Returns:
        True if authentication is required, False otherwise
    """
    # Check environment variable first (highest priority)
    env_require = os.getenv("REQUIRE_API_KEY", "").lower()
    if env_require in ("true", "1", "yes"):
        return True
    if env_require in ("false", "0", "no"):
        return False

    # Check config file
    try:
        cfg = get_config_service().get_config()
        security = getattr(cfg, "security", None)
        if security:
            return bool(security.require_api_key)
    except Exception as exc:
        logger.warning(f"Failed to read security config: {exc}")

    # Default: require authentication if API key is configured
    return _get_expected_api_key() is not None


def _is_secure_request(request: Request) -> bool:
    """
    判断请求是否为 HTTPS

    Args:
        request: FastAPI 请求对象

    Returns:
        True 如果是 HTTPS 请求，否则 False
    """
    # 检查 X-Forwarded-Proto 头（反向代理场景）
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
    if forwarded_proto:
        return forwarded_proto == "https"

    # 检查请求的 scheme
    if request.url.scheme == "https":
        return True

    # 开发环境检测（localhost 或 127.0.0.1）
    host = request.headers.get("host", "")
    if host.startswith("localhost:") or host.startswith("127.0.0.1:"):
        # 开发环境可以降级为非 Secure
        return os.getenv("COOKIE_SECURE", "true").lower() not in ("false", "0", "no")

    # 默认为 secure
    return True


def _extract_token_from_request(
    http_request: Request,
    x_api_key: str | None = None,
    authorization: str | None = None,
) -> str | None:
    """Extract auth token, preferring explicit request headers over ambient cookies."""
    if x_api_key:
        return x_api_key

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()

    token = http_request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        return token

    return None


def _can_bootstrap_init_admin(http_request: Request, db) -> bool:
    """Allow first admin bootstrap only when no admin exists and the request is trusted."""
    from app.models.user import User

    if User.has_admin(db):
        return False

    client_host = http_request.client.host if http_request.client else ""
    return client_host in {"127.0.0.1", "::1", "localhost"}


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response, http_request: Request):
    """
    用户登录

    支持两种认证方式：
    1. 用户名/密码登录
    2. API Key 登录
    """
    db = SessionLocal()
    try:
        cookie_max_age = get_access_token_max_age_seconds()
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent", "")

        if request.username and request.password:
            user, error_msg = AuthService.authenticate_user(
                db=db,
                username=request.username,
                password=request.password,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg or "用户名或密码错误")

            token = AuthService.create_access_token(user_id=user.id, username=user.username, role=user.role)
            refresh_token = AuthService.create_refresh_token(user_id=user.id)

            env = os.getenv("ENVIRONMENT", "development")
            is_production = env == "production"
            is_secure = is_production or _is_secure_request(http_request)
            samesite_policy = "strict" if is_production else "lax"

            response.set_cookie(
                key=AUTH_COOKIE_NAME,
                value=token,
                httponly=True,
                secure=is_secure,
                samesite=samesite_policy,
                max_age=cookie_max_age,
                path="/",
            )

            logger.info(f"User login successful: {user.username}")
            return LoginResponse(
                access_token=token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=cookie_max_age,
                user=UserResponse(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    role=user.role,
                    is_active=user.is_active,
                    created_at=str(user.created_at) if user.created_at else None,
                    last_login=str(user.last_login) if user.last_login else None,
                ),
            )

        if request.api_key:
            expected_key = _get_expected_api_key()
            if not expected_key:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="API key not configured")

            if not secrets.compare_digest(request.api_key, expected_key):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

            token = AuthService.create_access_token(user_id=0, username="api-key", role="api_key")
            refresh_token = AuthService.create_refresh_token(user_id=0)
            env = os.getenv("ENVIRONMENT", "development")
            is_production = env == "production"
            is_secure = is_production or _is_secure_request(http_request)
            samesite_policy = "strict" if is_production else "lax"

            response.set_cookie(
                key=AUTH_COOKIE_NAME,
                value=token,
                httponly=True,
                secure=is_secure,
                samesite=samesite_policy,
                max_age=cookie_max_age,
                path="/",
            )

            logger.info("API Key login successful")
            return LoginResponse(
                access_token=token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=cookie_max_age,
                user=None,
            )

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供用户名和密码，或 API Key")
    finally:
        db.close()


@router.get("/verify", response_model=VerifyResponse)
async def verify_token(
    http_request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """
    验证当前 Token 是否有效。

    支持从 Cookie、X-API-Key 或 Authorization 头读取凭证。
    JWT 与 API Key 都视为合法认证方式。
    """
    if not _is_auth_required():
        return VerifyResponse(valid=True, message="Authentication not required")

    provided_token = _extract_token_from_request(http_request, x_api_key, authorization)
    if not provided_token:
        return VerifyResponse(valid=False, message="No token provided")

    if AuthService.verify_access_token(provided_token):
        return VerifyResponse(valid=True, message="Token is valid")

    expected_key = _get_expected_api_key()
    if expected_key and secrets.compare_digest(provided_token, expected_key):
        return VerifyResponse(valid=True, message="Token is valid")

    return VerifyResponse(valid=False, message="Invalid token")


@router.post("/logout", response_model=LogoutResponse)
async def logout(response: Response):
    """
    登出

    清除 HttpOnly Cookie 中的 Token。
    """
    # 清除 Cookie
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
    )

    logger.info("Logout successful - cookie cleared")
    return LogoutResponse(success=True, message="Logout successful")


@router.get("/status")
async def auth_status(http_request: Request):
    """
    获取认证状态配置

    返回当前系统是否需要认证，供前端判断是否显示登录页面。
    """
    from app.models.user import User

    expected_key = _get_expected_api_key()
    auth_required = _is_auth_required()

    db = SessionLocal()
    try:
        has_admin_user = User.has_admin(db)
        can_init_admin = False if has_admin_user else _can_bootstrap_init_admin(http_request, db)

        return {
            "auth_required": auth_required,
            "has_api_key_configured": expected_key is not None,
            "message": "Authentication required" if auth_required else "No authentication required",
            "has_admin_user": has_admin_user,
            "can_init_admin": can_init_admin,
        }
    finally:
        db.close()


def _get_authenticated_user(http_request: Request, db):
    token = _extract_token_from_request(
        http_request,
        http_request.headers.get("X-API-Key"),
        http_request.headers.get("Authorization"),
    )
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

    payload = AuthService.decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 格式错误")

    from app.models.user import User

    user = User.get_by_id(db, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(request: RefreshTokenRequest):
    user_id = AuthService.verify_refresh_token(request.refresh_token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if user_id == 0:
        access_token = AuthService.create_access_token(user_id=0, username="api-key", role="api_key")
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=get_access_token_max_age_seconds(),
        )

    db = SessionLocal()
    try:
        from app.models.user import User

        user = User.get_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

        access_token = AuthService.create_access_token(user_id=user.id, username=user.username, role=user.role)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=get_access_token_max_age_seconds(),
        )
    finally:
        db.close()


@router.post("/change-password")
async def change_password(request: ChangePasswordRequest, http_request: Request):
    db = SessionLocal()
    try:
        user = _get_authenticated_user(http_request, db)

        success = AuthService.change_password(
            db=db,
            user=user,
            old_password=request.old_password,
            new_password=request.new_password,
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

        return {"success": True, "message": "Password changed successfully"}
    finally:
        db.close()


@router.get("/me", response_model=UserResponse)
async def get_current_user(http_request: Request):
    """
    获取当前登录用户信息

    从 Cookie 或 Authorization Header 中读取 Token 并验证。
    """
    db = SessionLocal()
    try:
        user = _get_authenticated_user(http_request, db)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=str(user.created_at) if user.created_at else None,
            last_login=str(user.last_login) if user.last_login else None,
        )
    finally:
        db.close()


@router.post("/init-admin", response_model=InitAdminResponse)
async def init_admin(http_request: Request):
    """
    初始化管理员账户

    仅允许在首次引导且请求受信任时创建管理员账户。
    """
    db = SessionLocal()
    try:
        from app.models.user import User

        if User.has_admin(db):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admin user already initialized")

        if not _can_bootstrap_init_admin(http_request, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Init-admin is only available for local first-time bootstrap",
            )

        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        configured_password = os.getenv("ADMIN_PASSWORD")
        if not configured_password:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Admin bootstrap password is not configured",
            )

        admin = AuthService.create_user(
            db=db,
            username=admin_username,
            password=configured_password,
            role="admin",
        )
        if admin:
            logger.info(f"Admin user initialized: {admin.username}")
            return InitAdminResponse(
                success=True,
                message="Admin user created successfully",
                username=admin.username,
                password_generated=False,
                generated_password=None,
            )
        return InitAdminResponse(
            success=False,
            message="Failed to create admin user",
            username="",
            password_generated=False,
            generated_password=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize admin",
        )
    finally:
        db.close()
