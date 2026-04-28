"""
夸克网盘文件大小获取器

用于获取夸克分享链接的文件大小信息

优化:
- 使用全局 HTTP 连接池，实现连接复用
- 降低 TCP 握手开销，减少延迟
- 统一管理 HTTP 客户端，降低内存占用
"""

import asyncio
import re
from datetime import datetime, timedelta

import httpx

from app.core.http_pool import ClientType, get_http_pool
from app.core.logging import get_logger


logger = get_logger(__name__)


class QuarkSizeCache:
    """夸克文件大小缓存"""

    def __init__(self, ttl_seconds: int = 3600):
        """
        初始化缓存

        Args:
            ttl_seconds: 缓存有效期（秒）
        """
        self._cache: dict[str, tuple[int, datetime]] = {}
        self._ttl = ttl_seconds

    def get(self, share_key: str) -> int | None:
        """
        获取缓存的大小

        Args:
            share_key: 分享密钥

        Returns:
            文件大小（字节），缓存不存在或过期返回 None
        """
        if share_key not in self._cache:
            return None

        size, timestamp = self._cache[share_key]
        if datetime.now() - timestamp > timedelta(seconds=self._ttl):
            del self._cache[share_key]
            return None

        return size

    def set(self, share_key: str, size: int):
        """
        设置缓存

        Args:
            share_key: 分享密钥
            size: 文件大小（字节）
        """
        self._cache[share_key] = (size, datetime.now())

    def clear(self):
        """清空缓存"""
        self._cache.clear()


class QuarkSizeFetcher:
    """夸克网盘文件大小获取器"""

    # 夸克分享链接正则
    SHARE_URL_PATTERN = re.compile(r"https?://pan\.quark\.cn/s/([a-zA-Z0-9_-]+)")

    def __init__(self, max_concurrent: int = 5):
        """
        初始化获取器

        Args:
            max_concurrent: 最大并发数
        """
        self._cache = QuarkSizeCache(ttl_seconds=3600)
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        # 不再创建独立客户端，使用全局连接池
        self._pool = None

    def extract_share_key(self, url: str) -> str | None:
        """
        从分享链接中提取分享密钥

        Args:
            url: 分享链接

        Returns:
            分享密钥，解析失败返回 None
        """
        match = self.SHARE_URL_PATTERN.search(url)
        if match:
            return match.group(1)
        return None

    async def get_share_size(self, share_key: str, password: str = "") -> int | None:
        """
        获取分享的总大小

        Args:
            share_key: 分享密钥
            password: 提取码

        Returns:
            总大小（字节），获取失败返回 None
        """
        # 检查缓存
        cached_size = self._cache.get(share_key)
        if cached_size is not None:
            return cached_size

        async with self._semaphore:
            try:
                # 从连接池获取客户端
                if self._pool is None:
                    self._pool = await get_http_pool()
                client = await self._pool.get_client(ClientType.QUARK)

                # 调用夸克 API 获取分享详情
                size = await self._fetch_share_size(share_key, password, client)

                if size is not None:
                    self._cache.set(share_key, size)

                return size

            except Exception as e:
                logger.warning(f"获取夸克分享大小失败: {share_key}, error: {e}")
                return None

    async def _fetch_share_size(self, share_key: str, password: str, client: httpx.AsyncClient) -> int | None:
        """
        实际获取分享大小的 HTTP 请求

        Args:
            share_key: 分享密钥
            password: 提取码
            client: HTTP客户端（来自连接池，不手动关闭）

        Returns:
            总大小（字节）
        """
        # 夸克分享详情 API
        api_url = "https://pan.quark.cn/share/sharepage/token"

        # 构建请求参数
        params = {"share_key": share_key, "passcode": password or ""}

        # 模拟浏览器的请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"https://pan.quark.cn/s/{share_key}",
            "Origin": "https://pan.quark.cn",
            "Connection": "keep-alive",
        }

        try:
            # 第一步：获取 token
            response = await client.post(api_url, data=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                logger.warning(f"获取分享 token 失败: {data.get('message')}")
                return None

            token = data.get("data", {}).get("token")
            if not token:
                return None

            # 第二步：获取文件列表
            list_url = "https://pan.quark.cn/share/sharepage/detail"
            headers["Authorization"] = f"Bearer {token}"

            total_size = 0
            page = 1

            while True:
                list_params = {
                    "share_key": share_key,
                    "passcode": password or "",
                    "page": page,
                    "size": 100,
                    "fetch_total": "true",
                }

                list_response = await client.get(list_url, params=list_params, headers=headers)
                list_response.raise_for_status()
                list_data = list_response.json()

                if list_data.get("code") != 0:
                    break

                items = list_data.get("data", {}).get("list", [])
                if not items:
                    break

                # 累加文件大小
                for item in items:
                    if item.get("file_type") == "0":  # 文件
                        total_size += item.get("file_size", 0)
                    elif item.get("file_type") == "1":  # 文件夹
                        # 递归获取文件夹内容
                        folder_size = await self._get_folder_size(
                            client, token, share_key, password, item.get("fid", ""), item.get("pdir_fid", "0")
                        )
                        total_size += folder_size

                # 检查是否还有更多
                total_count = list_data.get("data", {}).get("total_count", 0)
                if len(items) >= total_count or len(items) < 100:
                    break

                page += 1

            return total_size

        except Exception as e:
            logger.error(f"获取分享大小异常: {e}")
            return None

    async def _get_folder_size(
        self,
        client: httpx.AsyncClient,
        token: str,
        share_key: str,
        password: str,
        fid: str,
        pdir_fid: str,
        max_depth: int = 10,
    ) -> int:
        """
        迭代获取文件夹大小（避免递归深度问题）

        Args:
            client: HTTP客户端
            token: 访问令牌
            share_key: 分享密钥
            password: 提取码
            fid: 文件夹ID
            pdir_fid: 父目录ID
            max_depth: 最大递归深度，默认10层

        Returns:
            文件夹总大小（字节）
        """
        total_size = 0
        # 使用栈来模拟递归，避免深度过大
        folder_stack = [(fid, 0)]  # (folder_id, depth)
        processed_folders = set()  # 防止循环引用

        while folder_stack:
            current_fid, depth = folder_stack.pop()

            # 检查深度限制
            if depth > max_depth:
                logger.warning(f"文件夹深度超过限制 {max_depth}: {current_fid}")
                continue

            # 防止重复处理
            if current_fid in processed_folders:
                continue
            processed_folders.add(current_fid)

            page = 1
            while True:
                list_url = "https://pan.quark.cn/share/sharepage/detail"
                headers = {"Authorization": f"Bearer {token}"}

                params = {
                    "share_key": share_key,
                    "passcode": password or "",
                    "page": page,
                    "size": 100,
                    "pdir_fid": current_fid,
                }

                try:
                    response = await client.get(list_url, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                    if data.get("code") != 0:
                        break

                    items = data.get("data", {}).get("list", [])
                    if not items:
                        break

                    for item in items:
                        if item.get("file_type") == "0":  # 文件
                            total_size += item.get("file_size", 0)
                        elif item.get("file_type") == "1":  # 文件夹
                            # 将子文件夹加入栈中
                            sub_fid = item.get("fid", "")
                            if sub_fid and sub_fid not in processed_folders:
                                folder_stack.append((sub_fid, depth + 1))

                    if len(items) < 100:
                        break

                    page += 1

                except Exception as e:
                    logger.warning(f"获取文件夹大小失败: {current_fid}, error: {e}")
                    break

        return total_size

    async def batch_get_sizes(self, share_items: list[dict[str, str]], min_size_bytes: int = 0) -> dict[str, int]:
        """
        批量获取分享大小

        Args:
            share_items: 分享项列表，每项包含 url 和 password
            min_size_bytes: 最小大小（字节），用于过滤

        Returns:
            分享密钥到大小的映射
        """
        results = {}

        # 从连接池获取客户端
        if self._pool is None:
            self._pool = await get_http_pool()

        tasks = []

        for item in share_items:
            url = item.get("url", "")
            password = item.get("password", "")

            share_key = self.extract_share_key(url)
            if not share_key:
                continue

            task = self.get_share_size(share_key, password)
            tasks.append((share_key, task))

        # 并发执行
        for share_key, task in tasks:
            try:
                size = await task
                if size is not None and size >= min_size_bytes:
                    results[share_key] = size
            except Exception as e:
                logger.warning(f"批量获取大小失败: {share_key}, error: {e}")

        return results

    def format_size(self, size_bytes: int) -> str:
        """
        格式化大小为人类可读格式

        Args:
            size_bytes: 大小（字节）

        Returns:
            人类可读的大小字符串
        """
        if size_bytes == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"


# 全局单例
_size_fetcher: QuarkSizeFetcher | None = None


def get_size_fetcher() -> QuarkSizeFetcher:
    """获取全局大小获取器实例"""
    global _size_fetcher
    if _size_fetcher is None:
        _size_fetcher = QuarkSizeFetcher(max_concurrent=5)
    return _size_fetcher
