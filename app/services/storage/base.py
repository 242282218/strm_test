from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from app.schemas.file_manager import FileItem, StorageType

class StorageProvider(ABC):
    """
    存储提供者抽象基类
    """
    
    @property
    @abstractmethod
    def storage_type(self) -> StorageType:
        """返回存储类型"""
        pass
    
    @abstractmethod
    async def list(
        self, 
        path: str, 
        page: int = 1, 
        size: int = 100
    ) -> Tuple[List[FileItem], int, Optional[str]]:
        """列出目录内容: 返回 (列表, 总数, 父目录路径)"""
        pass
    
    @abstractmethod
    async def info(self, path: str) -> Optional[FileItem]:
        """获取单个文件/文件夹详情"""
        pass
    
    @abstractmethod
    async def rename(self, path: str, new_name: str) -> FileItem:
        """重命名"""
        pass
    
    @abstractmethod
    async def move_batch(self, source_paths: List[str], target_dir: str) -> bool:
        """批量移动文件"""
        pass

    @abstractmethod
    async def delete_batch(self, paths: List[str]) -> bool:
        """批量删除文件"""
        pass

    @abstractmethod
    async def move(self, source_path: str, target_dir: str) -> FileItem:
        """移动"""
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """删除"""
        pass
    
    @abstractmethod
    async def mkdir(self, parent_path: str, name: str) -> FileItem:
        """创建文件夹"""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """检查是否存在"""
        pass
