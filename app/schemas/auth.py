"""
认证相关 Schema

定义认证 API 的请求和响应模型
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    password: str = Field(..., min_length=4, max_length=128, description="密码")


class LoginResponse(BaseModel):
    """登录响应"""

    access_token: str = Field(..., description="JWT 访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="令牌过期时间（秒）")
    user: "UserInfo" = Field(..., description="用户信息")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""

    refresh_token: str = Field(..., description="刷新令牌")


class TokenResponse(BaseModel):
    """令牌响应"""

    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="令牌过期时间（秒）")


class UserInfo(BaseModel):
    """用户信息"""

    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    email: str | None = Field(None, description="邮箱地址")
    role: str = Field(..., description="用户角色")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime | None = Field(None, description="创建时间")
    last_login: datetime | None = Field(None, description="最后登录时间")

    model_config = ConfigDict(from_attributes=True)


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    old_password: str = Field(..., min_length=4, description="原密码")
    new_password: str = Field(..., min_length=4, max_length=128, description="新密码")


class UserCreate(BaseModel):
    """创建用户请求"""

    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    password: str = Field(..., min_length=4, max_length=128, description="密码")
    email: str | None = Field(None, description="邮箱地址")
    role: str = Field(default="user", description="用户角色")


class UserUpdate(BaseModel):
    """更新用户请求"""

    email: str | None = Field(None, description="邮箱地址")
    role: str | None = Field(None, description="用户角色")
    is_active: bool | None = Field(None, description="是否激活")


class AuthErrorResponse(BaseModel):
    """认证错误响应"""

    detail: str = Field(..., description="错误详情")
    error_code: str | None = Field(None, description="错误代码")


# 更新 LoginResponse 的 forward reference
LoginResponse.model_rebuild()
