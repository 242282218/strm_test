"""
Quark API client based on OpenList-compatible endpoints.

优化:
- 使用全局 HTTP 连接池，实现连接复用
- 降低 TCP 握手开销，减少延迟
- 统一管理 HTTP 客户端，降低内存占用
安全:
- SSRF 防护: 验证所有 API URL，防止访问内网资源
"""

from typing import Any

import httpx

from app.core.http_pool import ClientType, get_http_pool
from app.core.logging import get_logger
from app.core.retry import TransientError, retry_on_transient
from app.core.url_validator import URLValidationError, quark_validator


logger = get_logger(__name__)


class QuarkAPIClient:
    """HTTP client for Quark Cloud Drive APIs."""

    def __init__(
        self,
        cookie: str,
        referer: str = "https://pan.quark.cn/",
        timeout: int = 30,
        api_url: str = "https://drive.quark.cn/1/clouddrive",
    ):
        self.cookie = cookie
        self.referer = referer
        self.base_url = api_url.rstrip("/")
        self.timeout = timeout

        # SSRF 防护: 验证 API URL
        try:
            quark_validator.validate(self.base_url)
        except URLValidationError as e:
            logger.error(f"Invalid API URL (SSRF protection): {e}")
            raise ValueError(f"Invalid API URL: {e}")

        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 "
            "Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch"
        )
        # 使用全局连接池，不再独立管理 session
        self._pool = None
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（来自连接池）"""
        if self._client is None or self._client.is_closed:
            if self._pool is None:
                self._pool = await get_http_pool()
            self._client = await self._pool.get_client(ClientType.QUARK)
        return self._client

    @retry_on_transient()
    async def request(
        self,
        pathname: str,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send request to Quark API and return decoded JSON payload."""
        client = await self._get_client()

        url = f"{self.base_url}{pathname}"
        request_headers = {
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
            "Referer": self.referer,
            "User-Agent": self.user_agent,
        }
        if headers:
            request_headers.update(headers)

        query_params = {"pr": "ucpro", "fr": "pc"}
        if params:
            query_params.update(params)

        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=request_headers, params=query_params)
            elif method.upper() == "POST":
                response = await client.post(url, headers=request_headers, json=data, params=query_params)
            else:
                response = await client.request(method, url, headers=request_headers, json=data, params=query_params)

            # 更新 cookie（从响应头）
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

            status = int(result.get("status", response.status_code))
            code = int(result.get("code", 0))
            message = result.get("message", "")

            if status >= 500:
                raise TransientError(f"API transient error: {message} (status={status})")
            if status >= 400 or code != 0:
                error_msg = message or "Unknown error"
                logger.error(f"API error: {error_msg}, status: {status}, code: {code}")
                raise Exception(error_msg)

            return result
        except httpx.HTTPStatusError as exc:
            logger.error(f"Request failed: {exc}")
            raise TransientError(f"Request failed: {exc}") from exc
        except httpx.RequestError as exc:
            logger.error(f"Request failed: {exc}")
            raise TransientError(f"Request failed: {exc}") from exc
        except Exception:
            raise

    def _update_cookie(self, cookie_str: str, key: str, value: str) -> str:
        """Update one cookie key/value in a cookie string."""
        cookies: dict[str, str] = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                cookies[k.strip()] = v.strip()

        cookies[key] = value
        return "; ".join([f"{k}={v}" for k, v in cookies.items()])

    async def get_files(
        self,
        parent: str = "0",
        page_size: int = 100,
        order_by: str = "file_type",
        order_direction: str = "asc",
        only_video: bool = False,
    ) -> list[dict[str, Any]]:
        """List files under a parent directory."""
        files: list[dict[str, Any]] = []
        page = 1

        while True:
            query_params = {
                "pdir_fid": parent,
                "_size": str(page_size),
                "_fetch_total": "1",
                "fetch_all_file": "1",
                "fetch_risk_file_name": "1",
                "_page": str(page),
            }
            if order_by != "none":
                query_params["_sort"] = f"file_type:asc,{order_by}:{order_direction}"

            try:
                result = await self.request("/file/sort", params=query_params)
                data = result.get("data", {})
                file_list = data.get("list", [])
                metadata = data.get("metadata", {})

                for file_data in file_list:
                    file_data["file_name"] = file_data.get("file_name", "").replace("&amp;", "&")

                    if only_video:
                        is_dir = file_data.get("dir", False)
                        category = file_data.get("category", 0)
                        if not is_dir and category == 1:
                            files.append(file_data)
                    else:
                        files.append(file_data)

                total = int(metadata.get("total", 0))
                if total <= 0 or page * page_size >= total:
                    break
                page += 1
            except Exception as exc:
                logger.error("Failed to get files from %s: %s", parent, exc)
                break

        logger.debug("Got %d files from %s", len(files), parent)
        return files

    async def get_download_link(self, file_id: str) -> dict[str, Any]:
        """Get direct download link for a file."""
        data = {"fids": [file_id]}
        headers = {"User-Agent": self.user_agent}
        result = await self.request("/file/download", method="POST", data=data, headers=headers)

        raw_data = result.get("data") or []
        first = raw_data[0] if isinstance(raw_data, list) and raw_data else {}
        download_url = first.get("download_url", "")

        return {
            "url": download_url,
            "headers": {
                "Cookie": self.cookie,
                "Referer": self.referer,
                "User-Agent": self.user_agent,
            },
            "concurrency": 3,
            "part_size": 10 * 1024 * 1024,
        }

    async def get_transcoding_link(self, file_id: str) -> dict[str, Any]:
        """Get transcoding link for a playable stream."""
        data = {
            "fid": file_id,
            "resolutions": "low,normal,high,super,2k,4k",
            "supports": "fmp4_av,m3u8,dolby_vision",
        }
        headers = {"User-Agent": self.user_agent}
        result = await self.request("/file/v2/play/project", method="POST", data=data, headers=headers)

        video_list = result.get("data", {}).get("video_list", [])
        for info in video_list:
            video_info = info.get("video_info", {})
            url = video_info.get("url", "")
            if url:
                return {
                    "url": url,
                    "content_length": video_info.get("size", 0),
                    "concurrency": 3,
                    "part_size": 10 * 1024 * 1024,
                }

        raise Exception("No transcoding link found")

    async def get_share_token(self, pwd_id: str, passcode: str = "") -> str:
        """Get stoken for a share link."""
        payload = {"pwd_id": pwd_id, "passcode": passcode or ""}
        headers = {
            "Referer": f"https://pan.quark.cn/s/{pwd_id}",
            "Origin": "https://pan.quark.cn",
        }
        result = await self.request(
            "/share/sharepage/token",
            method="POST",
            data=payload,
            headers=headers,
        )
        return result.get("data", {}).get("stoken", "")

    async def get_share_files(self, pwd_id: str, stoken: str, pdir_fid: str = "0") -> list[dict[str, Any]]:
        """Get file list from shared resource."""
        files: list[dict[str, Any]] = []
        page = 1
        page_size = 100

        while True:
            params = {
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": pdir_fid,
                "_size": str(page_size),
                "_fetch_total": "1",
                "_page": str(page),
            }
            headers = {
                "Referer": f"https://pan.quark.cn/s/{pwd_id}",
                "Origin": "https://pan.quark.cn",
            }
            res = await self.request("/share/sharepage/detail", params=params, headers=headers)
            data = res.get("data", {})
            current = data.get("list", [])
            files.extend(current)

            metadata = res.get("metadata", {}) or {}
            total = int(metadata.get("_total", 0))
            count = int(metadata.get("_count", len(current)))

            if total > 0 and len(files) >= total:
                break
            if total <= 0 and count < page_size:
                break
            if not current:
                break

            page += 1

        return files

    async def save_share(self, pwd_id: str, stoken: str, fid_list: list[str], target_fid: str) -> dict[str, Any]:
        """Save shared files to my cloud drive."""
        data = {
            "fid_list": fid_list,
            "pwd_id": pwd_id,
            "stoken": stoken,
            # Newer share-save flow uses to_pdir_fid as destination.
            # Keep pdir_fid for compatibility with older behavior.
            "to_pdir_fid": target_fid,
            "pdir_fid": target_fid,
        }
        headers = {
            "Referer": f"https://pan.quark.cn/s/{pwd_id}",
            "Origin": "https://pan.quark.cn",
        }
        result = await self.request("/share/sharepage/save", method="POST", data=data, headers=headers)
        return result.get("data", {})

    async def delete_files(self, fids: list[str]):
        """Delete files or directories."""
        data = {"filelist": fids}
        await self.request("/file/delete", method="POST", data=data)

    async def create_directory(self, parent_fid: str, name: str) -> dict[str, Any]:
        """Create a directory."""
        data = {"pdir_fid": parent_fid, "file_name": name}
        result = await self.request("/file", method="POST", data=data)
        return result.get("data", {})

    async def rename_file(self, fid: str, new_name: str) -> dict[str, Any]:
        """Rename a file or directory."""
        data = {"fid": fid, "file_name": new_name}
        result = await self.request("/file/rename", method="POST", data=data)
        return result.get("data", {})

    async def get_file_info(self, fid: str) -> dict[str, Any]:
        """Get file metadata by fid."""
        result = await self.request("/file/info", method="GET", params={"fid": fid})
        return result.get("data", {})

    async def move_files(self, fids: list[str], to_pdir_fid: str) -> dict[str, Any]:
        """Move files or directories to target directory."""
        data = {"filelist": fids, "to_pdir_fid": to_pdir_fid}
        result = await self.request("/file/move", method="POST", data=data)
        return result.get("data", {})

    async def close(self):
        """关闭客户端（连接池统一管理，此方法保留兼容性）"""
        # 连接池统一管理客户端生命周期，这里只清理引用
        self._client = None
        logger.debug("QuarkAPIClient closed (connection pool managed)")
