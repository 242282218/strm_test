"""
STRM URL解析与构建工具
"""

from __future__ import annotations

import re
from typing import Optional
import aiofiles
from urllib.parse import urlparse


_PROXY_URL_RE = re.compile(r"/api/proxy/(?P<mode>redirect|stream|video)/(?P<file_id>[A-Za-z0-9]+)")


def build_proxy_url(proxy_base_url: str, file_id: str, mode: str = "redirect") -> str:
    """
    构建代理URL

    用途: 统一生成STRM中的代理直链
    输入:
        - proxy_base_url (str): 代理服务基础URL
        - file_id (str): 夸克文件ID
        - mode (str): 模式，redirect/stream/video
    输出:
        - str: 完整代理URL
    副作用:
        - 无
    """
    base = proxy_base_url.rstrip("/")
    return f"{base}/api/proxy/{mode}/{file_id}"


def extract_file_id_from_proxy_url(url: str) -> Optional[str]:
    """
    从代理URL中提取file_id

    用途: 解析STRM内容或PlaybackInfo中的代理URL
    输入:
        - url (str): 可能包含代理路径的URL
    输出:
        - Optional[str]: 提取到的file_id
    副作用:
        - 无
    """
    match = _PROXY_URL_RE.search(url)
    if match:
        return match.group("file_id")
    return None


def extract_file_id_from_strm_content(content: str) -> Optional[str]:
    """
    从STRM内容中提取file_id

    用途: 统一解析STRM文件内容获取file_id
    输入:
        - content (str): STRM文件内容
    输出:
        - Optional[str]: 提取到的file_id
    副作用:
        - 无
    """
    text = content.strip()
    if text.startswith("quark://"):
        return text.replace("quark://", "").strip()
    file_id = extract_file_id_from_proxy_url(text)
    if file_id:
        return file_id
    parsed = urlparse(text)
    if parsed.path:
        return extract_file_id_from_proxy_url(parsed.path)
    return None


async def read_strm_file_content(file_path: str) -> str:
    """
    读取STRM文件内容

    用途: 统一异步读取STRM文件内容
    输入:
        - file_path (str): STRM文件路径
    输出:
        - str: STRM文件内容
    副作用:
        - 读取文件
    """
    async with aiofiles.open(file_path, "r", encoding="utf-8") as handle:
        return (await handle.read()).strip()
