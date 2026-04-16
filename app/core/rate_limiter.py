"""
API 速率限制中间件

使用 slowapi 实现基于令牌桶算法的速率限制。
支持按 IP、用户、API 密钥等多维度限流。
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import ORJSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """速率限制配置"""

    requests: int  # 允许的请求数
    seconds: int  # 时间窗口（秒）
    block_duration: int = 60  # 超过限制后的封禁时长（秒）


@dataclass
class ClientState:
    """客户端状态"""

    requests: list[float] = field(default_factory=list)  # 请求时间戳列表
    blocked_until: float = 0  # 封禁结束时间
    total_requests: int = 0  # 总请求数
    blocked_count: int = 0  # 被封禁次数


class RateLimiter:
    """
    速率限制器

    使用滑动时间窗口算法实现限流。

    用法:
        limiter = RateLimiter()
        app.add_middleware(limiter.middleware)

        # 或者针对特定路由
        @app.post("/api/search")
        @limiter.limit(requests=10, seconds=60)
        async def search(request: Request):
            ...
    """

    def __init__(
        self,
        default_requests: int = 100,
        default_seconds: int = 60,
        default_block_duration: int = 300,
    ):
        """
        初始化速率限制器

        Args:
            default_requests: 默认允许的请求数
            default_seconds: 默认时间窗口（秒）
            default_block_duration: 默认封禁时长（秒）
        """
        self.default_config = RateLimitConfig(
            requests=default_requests,
            seconds=default_seconds,
            block_duration=default_block_duration,
        )
        self._client_states: dict[str, ClientState] = defaultdict(ClientState)
        self._route_configs: dict[str, RateLimitConfig] = {}
        self._cleanup_interval = 300  # 清理间隔（秒）
        self._last_cleanup = time.time()

    def limit(
        self,
        requests: int | None = None,
        seconds: int | None = None,
        block_duration: int | None = None,
    ) -> Callable:
        """
        装饰器：为特定路由设置速率限制

        Args:
            requests: 允许的请求数
            seconds: 时间窗口（秒）
            block_duration: 封禁时长（秒）

        Returns:
            装饰器函数
        """

        def decorator(func: Callable) -> Callable:
            import functools

            @functools.wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                config = RateLimitConfig(
                    requests=requests or self.default_config.requests,
                    seconds=seconds or self.default_config.seconds,
                    block_duration=block_duration or self.default_config.block_duration,
                )
                is_allowed, retry_after, block_reason = await self._check_rate_limit(request, config)

                if not is_allowed:
                    return self._create_rate_limit_response(retry_after, block_reason)

                return await func(request, *args, **kwargs)

            return wrapper

        return decorator

    async def _check_rate_limit(
        self, request: Request, config: RateLimitConfig
    ) -> tuple[bool, int, str | None]:
        """
        检查速率限制

        Args:
            request: FastAPI 请求
            config: 速率限制配置

        Returns:
            (是否允许，重试等待秒数，封禁原因)
        """
        client_id = self._get_client_id(request)
        now = time.time()

        # 清理过期数据
        self._cleanup_if_needed()

        state = self._client_states[client_id]

        # 检查是否在封禁期
        if state.blocked_until > now:
            remaining = int(state.blocked_until - now)
            return False, remaining, f"客户端已被封禁，请{remaining}秒后重试"

        # 移除时间窗口外的请求
        window_start = now - config.seconds
        state.requests = [t for t in state.requests if t > window_start]

        # 检查是否超过限制
        if len(state.requests) >= config.requests:
            # 超过限制，封禁客户端
            state.blocked_until = now + config.block_duration
            state.blocked_count += 1
            logger.warning(
                f"Rate limit exceeded for client {client_id}. "
                f"Blocked for {config.block_duration}s (count: {state.blocked_count})"
            )
            return False, config.block_duration, f"请求频率超限，已被封禁{config.block_duration}秒"

        # 记录请求
        state.requests.append(now)
        state.total_requests += 1

        return True, 0, None

    def _get_client_id(self, request: Request) -> str:
        """
        获取客户端唯一标识

        优先级：API Key > X-Forwarded-For > X-Real-IP > remote_addr
        """
        # 检查 API Key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key}"

        # 检查认证用户
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token_hash = hash(auth_header[7:])
            return f"user:{token_hash}"

        # 检查代理头部
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
            return f"ip:{ip}"

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return f"ip:{real_ip}"

        # 使用远程地址
        client_host = getattr(request, "client", None)
        if client_host and client_host.host:
            return f"ip:{client_host.host}"

        return "ip:unknown"

    def _create_rate_limit_response(self, retry_after: int, reason: str | None) -> Response:
        """创建速率限制响应"""
        return ORJSONResponse(
            status_code=429,
            content={
                "error": "Too Many Requests",
                "message": reason or "请求频率超限，请稍后重试",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    def _cleanup_if_needed(self):
        """清理过期数据"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        expired_clients = [
            client_id
            for client_id, state in self._client_states.items()
            if state.blocked_until < now and not state.requests
        ]

        for client_id in expired_clients:
            del self._client_states[client_id]

        logger.debug(f"Rate limiter cleanup: removed {len(expired_clients)} expired clients")

    def get_client_status(self, client_id: str) -> dict:
        """获取客户端状态"""
        state = self._client_states.get(client_id)
        if not state:
            return {"requests_made": 0, "blocked": False}

        now = time.time()
        return {
            "requests_made": len(state.requests),
            "total_requests": state.total_requests,
            "blocked": state.blocked_until > now,
            "blocked_until": state.blocked_until if state.blocked_until > now else None,
            "blocked_count": state.blocked_count,
        }

    def reset_client(self, client_id: str) -> bool:
        """重置客户端状态"""
        if client_id in self._client_states:
            del self._client_states[client_id]
            return True
        return False


# 全局速率限制器实例
_default_limiter: RateLimiter | None = None


def get_rate_limiter(
    requests: int = 100,
    seconds: int = 60,
    block_duration: int = 300,
) -> RateLimiter:
    """获取或创建全局速率限制器"""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter(
            default_requests=requests,
            default_seconds=seconds,
            default_block_duration=block_duration,
        )
    return _default_limiter


def setup_rate_limiting(app: FastAPI, requests: int = 100, seconds: int = 60, block_duration: int = 300):
    """
    为 FastAPI 应用设置速率限制

    Args:
        app: FastAPI 应用实例
        requests: 允许的请求数
        seconds: 时间窗口（秒）
        block_duration: 封禁时长（秒）
    """
    limiter = get_rate_limiter(requests, seconds, block_duration)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # 跳过健康检查和 metrics 端点
        if request.url.path in ["/health", "/health/live", "/health/ready", "/ready", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)

        is_allowed, retry_after, reason = await limiter._check_rate_limit(
            request, limiter.default_config
        )

        if not is_allowed:
            return limiter._create_rate_limit_response(retry_after, reason)

        response = await call_next(request)
        return response

    # 将 limiter 存储在 app.state 以便访问
    app.state.rate_limiter = limiter

    logger.info(f"Rate limiting enabled: {requests} requests / {seconds} seconds")
    return limiter
