import os
import shutil
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from app.services.storage.base import StorageProvider
from app.schemas.file_manager import FileItem, FileType, StorageType

class LocalStorageProvider(StorageProvider):
    """
    本地文件系统存储提供者
    """
    
    @property
    def storage_type(self) -> StorageType:
        return StorageType.LOCAL

    def _map_to_file_item(self, full_path: str) -> FileItem:
        """映射本地文件到 FileItem"""
        stat = os.stat(full_path)
        is_dir = os.path.isdir(full_path)
        file_name = os.path.basename(full_path)
        
        return FileItem(
            id=full_path, # 本地直接用路径作为 ID
            name=file_name,
            path=full_path,
            parent_path=os.path.dirname(full_path),
            file_type=FileType.FOLDER if is_dir else FileType.FILE,
            storage_type=StorageType.LOCAL,
            extension=os.path.splitext(file_name)[1][1:] if not is_dir else None,
            size=stat.st_size if not is_dir else 0,
            updated_at=datetime.fromtimestamp(stat.st_mtime),
            is_readable=os.access(full_path, os.R_OK),
            is_writable=os.access(full_path, os.W_OK)
        )

    async def list(
        self, 
        path: str, 
        page: int = 1, 
        size: int = 100
    ) -> Tuple[List[FileItem], int, Optional[str]]:
        """列出本地目录"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")
            
        items = []
        all_entries = os.listdir(path)
        total = len(all_entries)
        
        # 分页
        start = (page - 1) * size
        end = start + size
        paged_entries = sorted(all_entries)[start:end]
        
        for entry in paged_entries:
            full_path = os.path.join(path, entry)
            try:
                items.append(self._map_to_file_item(full_path))
            except Exception:
                continue
                
        # 计算父目录
        parent_path = os.path.dirname(os.path.abspath(path))
        # 如果当前路径就是根目录，dirname 还是它自己，设置为 None
        if parent_path == os.path.abspath(path):
            parent_path = None
            
        return items, total, parent_path

    async def info(self, path: str) -> Optional[FileItem]:
        if not os.path.exists(path):
            return None
        return self._map_to_file_item(path)

    async def rename(self, path: str, new_name: str) -> FileItem:
        parent = os.path.dirname(path)
        new_path = os.path.join(parent, new_name)
        os.rename(path, new_path)
        return self._map_to_file_item(new_path)

    async def move_batch(self, source_paths: List[str], target_dir: str) -> bool:
        """批量移动本地文件"""
        for path in source_paths:
            await self.move(path, target_dir)
        return True

    async def delete_batch(self, paths: List[str]) -> bool:
        """批量删除本地文件"""
        for path in paths:
            await self.delete(path)
        return True

    async def move(self, source_path: str, target_dir: str) -> FileItem:
        file_name = os.path.basename(source_path)
        target_path = os.path.join(target_dir, file_name)
        shutil.move(source_path, target_path)
        return self._map_to_file_item(target_path)

    async def delete(self, path: str) -> bool:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True

    async def mkdir(self, parent_path: str, name: str) -> FileItem:
        new_path = os.path.join(parent_path, name)
        os.makedirs(new_path, exist_ok=True)
        return self._map_to_file_item(new_path)

    async def exists(self, path: str) -> bool:
        return os.path.exists(path)
