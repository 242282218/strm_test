from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from app.services.storage.base import StorageProvider
from app.schemas.file_manager import FileItem, FileType, StorageType
from app.services.quark_service import QuarkService
from app.services.config_service import ConfigManager

class QuarkStorageProvider(StorageProvider):
    """
    夸克云盘存储提供者
    """
    
    def __init__(self, service: Optional[QuarkService] = None):
        if service:
            self.service = service
        else:
            config = ConfigManager()
            cookie = config.get("quark.cookie", "")
            self.service = QuarkService(cookie=cookie)
            
    @property
    def storage_type(self) -> StorageType:
        return StorageType.QUARK
    
    def _map_to_file_item(self, item: Dict[str, Any]) -> FileItem:
        """映射夸克原始数据到 FileItem"""
        # 夸克 file_type: 0 为目录, 1 为文件
        is_dir = item.get("file_type") == 0
        file_name = item.get("file_name", "Unknown")
        fid = item.get("fid", "")
        
        # 预览链接预留 (夸克支持视频预览预览)
        preview_url = None
        if not is_dir and item.get("category") == 1: # 视频
            # 可以在此处调用 get_transcoding_link，但为了性能通常在详情页加载
            pass

        return FileItem(
            id=fid,
            name=file_name,
            path=fid, # 夸克主要使用 ID 浏览
            parent_path=item.get("pdir_fid"),
            file_type=FileType.FOLDER if is_dir else FileType.FILE,
            storage_type=StorageType.QUARK,
            mime_type=None,
            extension=file_name.split('.')[-1] if '.' in file_name else None,
            size=item.get("size", 0),
            updated_at=datetime.fromtimestamp(item.get("updated_at", 0) / 1000.0) if item.get("updated_at") else None,
            thumbnail=item.get("thumbnail"),
            extra=item
        )

    async def list(
        self, 
        path: str, 
        page: int = 1, 
        size: int = 100
    ) -> Tuple[List[FileItem], int, Optional[str]]:
        """展示夸克目录内容"""
        # path 在夸克中对应 pdir_fid
        fid = path if path else "0"
        
        result = await self.service.list_files(pdir_fid=fid, page=page, size=size)
        items = result.get("list", [])
        metadata = result.get("metadata", {})
        
        # 尝试从元数据中获取总数
        total = metadata.get("_total", len(items))
        
        # 确定父目录：如果当前是根 '0'，则没有父目录
        parent_fid = None
        if fid != "0":
            # 优先从 list 接口返回的第一个 item 的 pdir_fid 获取 (夸克 API 通常会带上)
            if items:
                parent_fid = items[0].get("pdir_fid")
            else:
                # 如果目录为空，此处逻辑可能需要优化或通过缓存获取
                parent_fid = "0" 
        
        return [self._map_to_file_item(item) for item in items], total, parent_fid

    async def info(self, path: str) -> Optional[FileItem]:
        """获取夸克文件信息 (通过 fid)"""
        # 夸克没有直接获取单个 fid 信息的简单列表 API，
        # 通常需要列出父目录并过滤，或者使用 get_file_by_id (如果支持)
        # 暂时通过 list_files 根目录或缓存获取
        return None

    async def rename(self, path: str, new_name: str) -> FileItem:
        result = await self.service.rename_file(fid=path, new_name=new_name)
        # 由于 rename_file 返回的信息有限，返回部分构建的 FileItem
        return FileItem(
            id=path,
            name=new_name,
            path=path,
            file_type=FileType.FILE, # 这里可能不准，取决于调用者
            storage_type=StorageType.QUARK
        )

    async def move_batch(self, source_paths: List[str], target_dir: str) -> bool:
        """批量移动夸克文件"""
        if not source_paths:
            return True
        await self.service.client.move_files(fids=source_paths, to_pdir_fid=target_dir)
        return True

    async def delete_batch(self, paths: List[str]) -> bool:
        """批量删除夸克文件"""
        if not paths:
            return True
        await self.service.client.delete_files(fids=paths)
        return True

    async def move(self, source_path: str, target_dir: str) -> FileItem:
        await self.service.move_file(fid=source_path, to_pdir_fid=target_dir)
        return FileItem(id=source_path, name="Moved", path=source_path, storage_type=StorageType.QUARK, file_type=FileType.FILE)

    async def delete(self, path: str) -> bool:
        await self.service.delete_file(fid=path)
        return True

    async def mkdir(self, parent_path: str, name: str) -> FileItem:
        result = await self.service.mkdir(parent_fid=parent_path, name=name)
        # mkdir API may return only {"fid": "..."}; enrich for stable response fields.
        normalized = dict(result or {})
        normalized.setdefault("fid", normalized.get("id", ""))
        normalized.setdefault("file_name", name)
        normalized.setdefault("pdir_fid", parent_path)
        normalized.setdefault("file_type", 0)
        normalized.setdefault("size", 0)
        return self._map_to_file_item(normalized)

    async def exists(self, path: str) -> bool:
        return True # 暂时默认存在
