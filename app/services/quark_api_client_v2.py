"""
夸克API客户端（基于OpenList实现）

参考: OpenList drivers/quark_uc/util.go
"""

import aiohttp
import json
from typing import Optional, Dict, Any, List
from app.core.logging import get_logger
from app.core.retry import retry_on_transient, TransientError

logger = get_logger(__name__)


class QuarkAPIClient:
    """
    夸克API客户端

    参考: OpenList QuarkOrUC.request方法
    """

    def __init__(self, cookie: str, referer: str = "https://pan.quark.cn/", timeout: int = 30, api_url: str = "https://drive.quark.cn/1/clouddrive"):
        """
        初始化客户端

        Args:
            cookie: 夸克Cookie
            referer: Referer地址
            timeout: 请求超时时间（秒）
            api_url: API基础URL
        """
        self.cookie = cookie
        self.referer = referer
        self.base_url = api_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch"

    async def _ensure_session(self):
        """确保session已初始化"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout, connector=aiohttp.TCPConnector(limit=10))

    @retry_on_transient()
    async def request(
        self,
        pathname: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        通用请求方法

        参考: OpenList quark_uc/util.go:27-67

        Args:
            pathname: API路径
            method: HTTP方法
            data: 请求数据
            params: 查询参数
            headers: 额外的请求头

        Returns:
            响应数据字典

        Raises:
            Exception: 请求失败时抛出异常
        """
        await self._ensure_session()

        url = f"{self.base_url}{pathname}"

        request_headers = {
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
            "Referer": self.referer,
            "User-Agent": self.user_agent
        }

        if headers:
            request_headers.update(headers)

        query_params = {"pr": "ucpro", "fr": "pc"}
        if params:
            query_params.update(params)

        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=request_headers,
                json=data,
                params=query_params
            ) as response:
                result = await response.json()

                # 更新Cookie（__puus/__pus）
                for cookie_key in ["__puus", "__pus"]:
                    if cookie_key in response.cookies:
                        cookie = response.cookies[cookie_key]
                        self.cookie = self._update_cookie(self.cookie, cookie_key, cookie.value)
                        logger.debug(f"Updated cookie: {cookie_key}")

                # 检查响应状态
                status = result.get("status", 0)
                code = result.get("code", 0)
                message = result.get("message", "")

                if status >= 500:
                    raise TransientError(f"API transient error: {message} (status={status})")
                if status >= 400 or code != 0:
                    error_msg = message or "Unknown error"
                    logger.error(f"API error: {error_msg}, status: {status}, code: {code}")
                    raise Exception(error_msg)

                return result

        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {str(e)}")
            raise TransientError(f"Request failed: {str(e)}") from e
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

    async def get_files(
        self,
        parent: str = "0",
        page_size: int = 100,
        order_by: str = "file_type",
        order_direction: str = "asc",
        only_video: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取文件列表

        参考: OpenList quark_uc/util.go:69-111

        Args:
            parent: 父目录ID
            page_size: 每页大小
            order_by: 排序字段
            order_direction: 排序方向
            only_video: 是否只获取视频文件

        Returns:
            文件列表
        """
        files = []
        page = 1

        while True:
            query_params = {
                "pdir_fid": parent,
                "_size": str(page_size),
                "_fetch_total": "1",
                "fetch_all_file": "1",
                "fetch_risk_file_name": "1",
                "_page": str(page)
            }

            if order_by != "none":
                query_params["_sort"] = f"file_type:asc,{order_by}:{order_direction}"

            try:
                result = await self.request("/file/sort", params=query_params)
                data = result.get("data", {})
                file_list = data.get("list", [])
                metadata = data.get("metadata", {})

                for file_data in file_list:
                    # HTML转义处理
                    file_data["file_name"] = file_data.get("file_name", "").replace("&amp;", "&")

                    # 过滤视频文件
                    if only_video:
                        is_dir = file_data.get("dir", False)
                        category = file_data.get("category", 0)
                        if not is_dir and category == 1:
                            files.append(file_data)
                    else:
                        files.append(file_data)

                # 检查是否还有更多页
                total = metadata.get("total", 0)
                if page * page_size >= total:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Failed to get files from {parent}: {str(e)}")
                break

        logger.debug(f"Got {len(files)} files from {parent}")
        return files

    async def get_download_link(self, file_id: str) -> Dict[str, Any]:
        """
        获取下载直链

        参考: OpenList quark_uc/util.go:113-137

        Args:
            file_id: 文件ID

        Returns:
            直链信息
        """
        data = {
            "fids": [file_id]
        }

        headers = {
            "User-Agent": self.user_agent
        }

        result = await self.request("/file/download", method="POST", data=data, headers=headers)

        download_url = result.get("data", [{}])[0].get("download_url", "")

        return {
            "url": download_url,
            "headers": {
                "Cookie": self.cookie,
                "Referer": self.referer,
                "User-Agent": self.user_agent
            },
            "concurrency": 3,
            "part_size": 10 * 1024 * 1024  # 10MB
        }

    async def get_transcoding_link(self, file_id: str) -> Dict[str, Any]:
        """
        获取转码直链

        参考: OpenList quark_uc/util.go:139-168

        Args:
            file_id: 文件ID

        Returns:
            转码直链信息
        """
        data = {
            "fid": file_id,
            "resolutions": "low,normal,high,super,2k,4k",
            "supports": "fmp4_av,m3u8,dolby_vision"
        }

        headers = {
            "User-Agent": self.user_agent
        }

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
                    "part_size": 10 * 1024 * 1024  # 10MB
                }

        raise Exception("No transcoding link found")

    async def get_share_token(self, pwd_id: str, passcode: str = "") -> str:
        """获取分享Token (stoken)"""
        await self._ensure_session()
        params = {"pwd_id": pwd_id}
        if passcode:
            params["passcode"] = passcode
            
        url = "https://pan.quark.cn/share/sharepage/token"
        
        headers = {
            "Cookie": self.cookie,
            "User-Agent": self.user_agent,
            "Referer": f"https://pan.quark.cn/s/{pwd_id}"
        }
        
        try:
            async with self.session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                if data.get("code") != 0:
                    # 某些情况下不需要 stoken 也能访问？或者错误信息不同
                    # logging
                    logger.warning(f"Get stoken result: {data}")
                    return ""
                return data.get("data", {}).get("stoken", "")
        except Exception as e:
            logger.error(f"Failed to get share token: {e}")
            raise

    async def get_share_files(self, pwd_id: str, stoken: str, pdir_fid: str = "0") -> List[Dict[str, Any]]:
        """获取分享文件列表"""
        params = {
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": pdir_fid,
            "_size": "100",  # 通常我们只转存根目录下的内容
            "_fetch_total": "1",
            "share_id": pwd_id # 有些接口可能需要 share_id
        }
        
        # 尝试调用 /share/sort
        # 注意：如果 pdir_fid是 "0" (分享根目录), 某些实现可能不同
        try:
            res = await self.request("/share/sort", params=params)
            return res.get("data", {}).get("list", [])
        except Exception as e:
            logger.error(f"Failed to get share files: {e}")
            raise

    async def save_share(self, pwd_id: str, stoken: str, fid_list: List[str], target_fid: str):
        """转存文件"""
        data = {
            "fid_list": fid_list,
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": target_fid # 目标文件夹ID
        }
        try:
            await self.request("/share/save", method="POST", data=data)
        except Exception as e:
            logger.error(f"Save share failed: {e}")
            raise

    async def delete_files(self, fids: List[str]):
        """删除文件/文件夹"""
        data = {
            "filelist": fids  # 夸克 API 使用 filelist
        }
        try:
            await self.request("/file/delete", method="POST", data=data)
        except Exception as e:
            logger.error(f"Delete files failed: {e}")
            raise

    async def create_directory(self, parent_fid: str, name: str) -> Dict[str, Any]:
        """创建文件夹"""
        data = {
            "pdir_fid": parent_fid,
            "file_name": name
        }
        try:
            result = await self.request("/file", method="POST", data=data)
            return result.get("data", {})
        except Exception as e:
            logger.error(f"Create directory failed: {e}")
            raise

    async def rename_file(self, fid: str, new_name: str) -> Dict[str, Any]:
        """重命名文件/文件夹"""
        data = {
            "fid": fid,
            "file_name": new_name
        }
        try:
            result = await self.request("/file/rename", method="POST", data=data)
            return result.get("data", {})
        except Exception as e:
            logger.error(f"Rename file failed: {e}")
            raise

    async def move_files(self, fids: List[str], to_pdir_fid: str) -> Dict[str, Any]:
        """移动文件/文件夹"""
        data = {
            "filelist": fids,  # 夸克 API 使用 filelist 而不是 fids
            "to_pdir_fid": to_pdir_fid
        }
        try:
            result = await self.request("/file/move", method="POST", data=data)
            return result.get("data", {})
        except Exception as e:
            logger.error(f"Move files failed: {e}")
            raise

    async def close(self):
        """关闭session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("QuarkAPIClient session closed")
