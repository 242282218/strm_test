"""
夸克API客户端

参考: OpenList quark_uc/util.go:27-67
"""

import aiohttp
from typing import Optional, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)


class QuarkAPIClient:
    """
    夸克API客户端

    参考: OpenList QuarkOrUC.request方法
    """

    def __init__(self, cookie: str, referer: str = "https://pan.quark.cn/", timeout: int = 30):
        """
        初始化客户端

        Args:
            cookie: 夸克Cookie
            referer: Referer地址
            timeout: 请求超时时间（秒）
        """
        self.cookie = cookie
        self.referer = referer
        self.base_url = "https://pan.quark.cn"
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def _ensure_session(self):
        """确保session已初始化"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout, connector=aiohttp.TCPConnector(limit=10))

    async def request(
        self,
        pathname: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
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
        await self._ensure_session()

        url = f"{self.base_url}/uc{pathname}"
        headers = {
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
            "Referer": self.referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        query_params = {"pr": "uc", "fr": "pc"}
        if params:
            query_params.update(params)

        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=query_params
            ) as response:
                result = await response.json()

                # 更新Cookie
                for cookie_key in response.cookies:
                    if cookie_key in ["__puus", "__pus"]:
                        cookie = response.cookies[cookie_key]
                        self.cookie = self._update_cookie(self.cookie, cookie_key, cookie.value)
                        logger.debug(f"Updated cookie: {cookie_key}")

                # 检查响应状态
                status = result.get("status", 0)
                code = result.get("code", 0)
                message = result.get("message", "")

                if status >= 400 or code != 0:
                    error_msg = message or "Unknown error"
                    logger.error(f"API error: {error_msg}, status: {status}, code: {code}")
                    raise Exception(error_msg)

                return result

        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {str(e)}")
            raise Exception(f"Request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

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
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("QuarkAPIClient session closed")
