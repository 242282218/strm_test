"""
夸克API客户端

参考: OpenList quark_uc/util.go:27-67

优化:
- 支持 use_pool 参数，默认使用全局 HTTP 连接池
- 降低 TCP 握手开销，减少延迟
- 保留 legacy_mode 参数允许使用独立客户端
"""

import os
from typing import Any

import aiohttp
import httpx

from app.core.http_pool import ClientType, get_http_pool
from app.core.logging import get_logger


logger = get_logger(__name__)


class QuarkAPIClient:
    """
    夸克API客户端

    参考: OpenList QuarkOrUC.request方法

    Args:
        cookie: 夸克Cookie
        referer: Referer地址
        timeout: 请求超时时间（秒）
        use_pool: 是否使用全局连接池（默认True）
        legacy_mode: 是否使用旧版独立session（默认False，优先级高于use_pool）
    """

    def __init__(
        self,
        cookie: str,
        referer: str = "https://pan.quark.cn/",
        timeout: int = 30,
        use_pool: bool = True,
        legacy_mode: bool = False,
    ):
        """
        初始化客户端

        Args:
            cookie: 夸克Cookie
            referer: Referer地址
            timeout: 请求超时时间（秒）
            use_pool: 是否使用全局连接池（默认True）
            legacy_mode: 是否使用旧版独立session（默认False）
        """
        self.cookie = cookie
        self.referer = referer
        self.base_url = "https://pan.quark.cn"

        # 超时配置（aiohttp 的 ClientTimeout），同时保留秒数供 httpx 传递
        self._aiohttp_timeout = aiohttp.ClientTimeout(total=timeout)
        self.timeout = self._aiohttp_timeout
        self.timeout_seconds = timeout
        self.use_pool = use_pool and not legacy_mode
        # 在测试环境默认禁用连接池，使用可打桩的 aiohttp session
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SMART_MEDIA_TESTING") == "1":
            self.use_pool = False
        self.legacy_mode = legacy_mode

        # 旧版独立 session（仅 legacy_mode 或禁用池时使用）
        self.session: aiohttp.ClientSession | None = None

        # 连接池客户端
        self._pool = None
        self._httpx_client: httpx.AsyncClient | None = None

    async def _ensure_session(self):
        """确保session已初始化（旧版兼容）"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self._aiohttp_timeout, connector=aiohttp.TCPConnector(limit=10)
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（来自连接池）"""
        if self._httpx_client is None or self._httpx_client.is_closed:
            if self._pool is None:
                self._pool = await get_http_pool()
            self._httpx_client = await self._pool.get_client(ClientType.QUARK)
        return self._httpx_client

    async def request(
        self,
        pathname: str,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        通用请求方法

        参考: OpenList quark_uc/util.go:27-67

        Args:
            pathname: API路径
            method: HTTP方法
            data: 请求数据
            params: 查询参数

        Returns:
            响应数据字典

        Raises:
            Exception: 请求失败时抛出异常
        """
        url = f"{self.base_url}/uc{pathname}"
        headers = {
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
            "Referer": self.referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        query_params = {"pr": "uc", "fr": "pc"}
        if params:
            query_params.update(params)

        # 根据配置选择使用连接池还是独立 session
        if self.use_pool:
            return await self._request_with_pool(url, method, headers, data, query_params)
        return await self._request_with_session(url, method, headers, data, query_params)

    async def _request_with_pool(
        self, url: str, method: str, headers: dict[str, str], data: dict[str, Any] | None, query_params: dict[str, str]
    ) -> dict[str, Any]:
        """使用连接池发送请求"""
        client = await self._get_client()

        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=query_params, timeout=self.timeout_seconds)
            elif method.upper() == "POST":
                response = await client.post(
                    url, headers=headers, json=data, params=query_params, timeout=self.timeout_seconds
                )
            else:
                response = await client.request(
                    method, url, headers=headers, json=data, params=query_params, timeout=self.timeout_seconds
                )

            # 更新 Cookie（从响应头）
            set_cookie = response.headers.get("set-cookie", "")
            if set_cookie:
                for cookie_part in set_cookie.split(";"):
                    if "=" in cookie_part:
                        key_val = cookie_part.strip().split("=", 1)
                        if len(key_val) == 2:
                            key, value = key_val
                            if key in ["__puus", "__pus"]:
                                self.cookie = self._update_cookie(self.cookie, key, value)
                                logger.debug(f"Updated cookie: {key}")

            result = response.json()

            self._raise_for_api_error(result)
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Request failed: {e!s}")
            raise Exception(f"Request failed: {e!s}")
        except httpx.RequestError as e:
            logger.error(f"Request failed: {e!s}")
            raise Exception(f"Request failed: {e!s}")
        except Exception:
            raise

    def _raise_for_api_error(self, result: dict[str, Any]) -> None:
        status = result.get("status", 0)
        code = result.get("code", 0)
        message = result.get("message", "")

        if status >= 400 or code != 0:
            error_msg = message or "Unknown error"
            logger.error(f"API error: {error_msg}, status: {status}, code: {code}")
            raise Exception(error_msg)

    async def _parse_session_response(self, response: Any) -> dict[str, Any]:
        result = await response.json()

        # 更新Cookie
        for cookie_key in response.cookies:
            if cookie_key in ["__puus", "__pus"]:
                cookie = response.cookies[cookie_key]
                self.cookie = self._update_cookie(self.cookie, cookie_key, cookie.value)
                logger.debug(f"Updated cookie: {cookie_key}")

        self._raise_for_api_error(result)
        return result

    async def _request_with_session(
        self, url: str, method: str, headers: dict[str, str], data: dict[str, Any] | None, query_params: dict[str, str]
    ) -> dict[str, Any]:
        """使用独立 session 发送请求（旧版兼容）"""
        await self._ensure_session()

        try:
            request_result = self.session.request(
                method=method, url=url, headers=headers, json=data, params=query_params
            )

            if hasattr(request_result, "__aenter__") and hasattr(request_result, "__aexit__"):
                return await self._consume_request_context_manager(request_result)

            if hasattr(request_result, "__await__"):
                response = await request_result
                return await self._parse_session_response(response)

            if hasattr(request_result, "json") and hasattr(request_result, "cookies"):
                return await self._parse_session_response(request_result)

            raise TypeError("Unsupported session.request return type")

        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {e!s}")
            raise Exception(f"Request failed: {e!s}")
        except Exception as e:
            logger.error(f"Unexpected error: {e!s}")
            raise

    async def _consume_request_context_manager(self, request_result: Any) -> dict[str, Any]:
        response = await request_result.__aenter__()
        exc_info: tuple[type[BaseException], BaseException, Any] | None = None
        try:
            return await self._parse_session_response(response)
        except Exception as exc:
            exc_info = (type(exc), exc, exc.__traceback__)
            raise
        finally:
            if exc_info is None:
                await request_result.__aexit__(None, None, None)
            else:
                await request_result.__aexit__(*exc_info)

    def _update_cookie(self, cookie_str: str, key: str, value: str) -> str:
        """
        更新Cookie

        Args:
            cookie_str: 原Cookie字符串
            key: 要更新的Cookie键
            value: 新的Cookie值

        Returns:
            更新后的Cookie字符串
        """
        cookies = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                cookies[k.strip()] = v.strip()

        cookies[key] = value
        return "; ".join([f"{k}={v}" for k, v in cookies.items()])

    async def close(self):
        """关闭session"""
        # 关闭旧版独立 session
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("QuarkAPIClient session closed")

        # 连接池统一管理客户端生命周期，这里只清理引用
        self._httpx_client = None
        logger.debug("QuarkAPIClient closed")
