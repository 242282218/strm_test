import mimetypes
from wsgidav.dav_provider import DAVCollection, DAVNonCollection
from wsgidav.dav_error import DAVError
from app.services.quark_service import QuarkService
from app.core.logging import get_logger
import asyncio
import threading

logger = get_logger(__name__)

class QuarkResource:
    """Quark资源基类"""
    def __init__(self, path, environ, file_info, provider):
        self.path = path
        self.environ = environ
        self.file_info = file_info
        self.provider = provider
        self.quark_service = provider.quark_service

class QuarkFolderResource(DAVCollection, QuarkResource):
    """Quark网盘目录资源"""
    
    def __init__(self, path, environ, file_info, provider):
        DAVCollection.__init__(self, path, environ)
        QuarkResource.__init__(self, path, environ, file_info, provider)

    def get_member_names(self):
        """获取子文件名称列表"""
        return [f.file_name for f in self._get_children()]

    def get_member(self, name):
        """获取子资源对象"""
        children = self._get_children()
        for child in children:
            if child.file_name == name:
                path = f"{self.path}/{name}".replace("//", "/")
                if child.is_dir:
                    return QuarkFolderResource(path, self.environ, child, self.provider)
                else:
                    return QuarkFileResource(path, self.environ, child, self.provider)
        return None

    def _get_children(self):
        """获取子文件列表（带缓存）"""
        # 注意：这里涉及到 async 调用，需要同步转换
        fid = self.file_info.fid if self.file_info else "0"
        
        # 使用 provider 的辅助方法执行异步
        try:
            return self.provider.sync_call(
                self.quark_service.get_files(parent=fid)
            )
        except Exception as e:
            logger.error(f"Failed to get children for {fid}: {e}")
            raise DAVError(500, str(e))

class QuarkFileResource(DAVNonCollection, QuarkResource):
    """Quark网盘文件资源"""
    
    def __init__(self, path, environ, file_info, provider):
        DAVNonCollection.__init__(self, path, environ)
        QuarkResource.__init__(self, path, environ, file_info, provider)

    def get_content_length(self):
        return self.file_info.size

    def get_content_type(self):
        return mimetypes.guess_type(self.path)[0]

    def get_creation_date(self):
        return self._safe_timestamp(self.file_info.created_at)

    def get_last_modified(self):
        return self._safe_timestamp(self.file_info.updated_at)
        
    def _safe_timestamp(self, ts):
        if not ts:
            return None
        try:
            ts = float(ts)
            # 如果时间戳是毫秒级的（大于 3000年），转换为秒
            if ts > 32503680000: 
                ts = ts / 1000.0
            return ts
        except:
            return None

    def get_content(self):
        """
        获取文件内容。
        核心逻辑：优先跳转到可直接播放的转码链接。
        """
        try:
            # 优先使用转码链接：通常无需夸克 Cookie/Referer，播放器兼容性更高
            link = self.provider.sync_call(
                self.quark_service.get_transcoding_link(self.file_info.fid)
            )
            if not link or not getattr(link, "url", None):
                # 兜底到下载链接（部分环境可能需要特定请求头）
                link = self.provider.sync_call(
                    self.quark_service.get_download_link(self.file_info.fid)
                )

            logger.info(f"Redirecting {self.path} to {link.url[:50]}...")
            raise DAVError(307, add_headers=[("Location", link.url)])

        except DAVError:
            raise
        except Exception as e:
            logger.error(f"Failed to get content for {self.path}: {e}")
            raise DAVError(500, str(e))

    def support_etag(self):
        """是否支持 ETag"""
        return False

    def get_etag(self):
        """获取 ETag"""
        return None

