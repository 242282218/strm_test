"""
STRM URL解析与构建工具
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, quote, unquote, urlparse

import aiofiles


_PROXY_URL_RE = re.compile(r"/api/proxy/(?P<mode>redirect|stream|video)/(?P<file_id>[A-Za-z0-9]+)")
_STABLE_MEDIA_URL_RE = re.compile(
    r"/strm/v1/m/(?P<media_id>[A-Za-z0-9_.:-]+)/(?P<display_name>[^?#]+)",
)


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


def build_stable_media_url(proxy_base_url: str, media_id: str, display_name: str) -> str:
    """
    构建稳定媒体入口 URL。
    """
    base = proxy_base_url.rstrip("/")
    encoded_display_name = quote(display_name, safe="()[]-_.")
    return f"{base}/strm/v1/m/{media_id}/{encoded_display_name}"


def extract_file_id_from_proxy_url(url: str) -> str | None:
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


def extract_media_id_from_url(url: str) -> str | None:
    """
    从稳定媒体入口中提取 media_id。
    """
    parsed = urlparse(url)
    candidates = [parsed.path or "", (url or "").strip()]
    for candidate in candidates:
        match = _STABLE_MEDIA_URL_RE.search(candidate)
        if match:
            return match.group("media_id")
    return None


def extract_display_name_from_url(url: str) -> str | None:
    """
    从稳定媒体入口中提取展示文件名。
    """
    parsed = urlparse(url)
    candidates = [parsed.path or "", (url or "").strip()]
    for candidate in candidates:
        match = _STABLE_MEDIA_URL_RE.search(candidate)
        if match:
            return unquote(match.group("display_name"))
    return None


def is_stable_media_url(url: str) -> bool:
    return extract_media_id_from_url(url or "") is not None


def extract_path_from_media_reference(reference: str) -> str | None:
    """
    从兼容 URL 中提取 path 查询参数。
    """
    parsed = urlparse(reference or "")
    values = parse_qs(parsed.query).get("path", [])
    if not values:
        return None
    return unquote(values[0]).strip() or None


def extract_file_id_from_strm_content(content: str) -> str | None:
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


def extract_media_id_from_strm_content(content: str) -> str | None:
    """
    从 STRM 内容中提取稳定 media_id。
    """
    text = content.strip()
    return extract_media_id_from_url(text)


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
    async with aiofiles.open(file_path, encoding="utf-8") as handle:
        return (await handle.read()).strip()
