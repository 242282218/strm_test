from asgiref.sync import async_to_sync
from wsgidav.dav_error import DAVError
from wsgidav.dav_provider import DAVProvider

from app.core.logging import get_logger
from app.services.cache_service import get_cache_service
from app.services.config_service import get_config_service
from app.services.quark_service import QuarkService

from .resource import QuarkFileResource, QuarkFolderResource


logger = get_logger(__name__)


class QuarkDAVProvider(DAVProvider):
    """Quark网盘 WebDAV 提供者"""

    def __init__(self):
        super().__init__()
        self.config_service = get_config_service()
        self.config = self.config_service.get_config()
        self.cache_service = get_cache_service()

        # 初始化 QuarkService (单例获取或新建)
        cookie = self.config.quark.cookie
        if not cookie:
            logger.warning("Quark cookie not found in config, WebDAV might not work.")

        self.quark_service = QuarkService(cookie=cookie)

    def sync_call(self, coro):
        """同步调用异步方法"""
        return async_to_sync(lambda: coro)()

    def get_resource_inst(self, path, environ):
        """
        解析路径返回资源实例
        WebDAV 核心入口
        """
        path = path.strip("/")
        # logger.debug(f"WebDAV request: {raw_path} -> {path}")

        try:
            if not path:
                return QuarkFolderResource("/", environ, None, self)

            # 1. 尝试从缓存获取
            cache_key = f"webdav:path:{path}"

            async def get_cached_or_remote():
                cached = await self.cache_service.get(cache_key)
                if cached:
                    return cached

                # 未命中，查询远程
                info = await self.quark_service.get_file_by_path(path)
                if info:
                    # 写入缓存，TTL 5分钟
                    await self.cache_service.set(cache_key, info, ttl=300)
                return info

            file_info = self.sync_call(get_cached_or_remote())

            if not file_info:
                # logger.debug(f"Path not found: {path}")
                return None

            # logger.debug(f"Found file: {file_info.file_name} (dir={file_info.is_dir})")

            resource_path = f"/{path}"

            if file_info.is_dir:
                return QuarkFolderResource(resource_path, environ, file_info, self)
            return QuarkFileResource(resource_path, environ, file_info, self)

        except Exception as e:
            import traceback

            logger.error(f"Error resolving path {path}: {e}\n{traceback.format_exc()}")
            if "not found" in str(e).lower():
                return None
            raise DAVError(500, f"Error resolving path {path}: {e!s}")
