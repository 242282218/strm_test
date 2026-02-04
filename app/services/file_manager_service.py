from typing import List, Optional, Dict
from fastapi import HTTPException
from app.schemas.file_manager import (
    FileItem, StorageType, BrowseResponse, 
    FileOperationRequest, FileOperationAction, FileType
)
from app.services.storage.base import StorageProvider
from app.services.storage.local import LocalStorageProvider
from app.services.storage.quark import QuarkStorageProvider
from app.core.logging import get_logger

logger = get_logger(__name__)

class FileManagerService:
    """
    文件管理统一服务 (门面模式)
    """
    
    def __init__(self):
        self._providers: Dict[StorageType, StorageProvider] = {
            StorageType.LOCAL: LocalStorageProvider(),
            StorageType.QUARK: QuarkStorageProvider()
        }

    def _get_provider(self, storage_type: StorageType) -> StorageProvider:
        provider = self._providers.get(storage_type)
        if not provider:
            raise HTTPException(status_code=400, detail=f"Storage type {storage_type} not supported")
        return provider

    async def browse(
        self, 
        storage_type: StorageType, 
        path: str = "/", 
        page: int = 1, 
        size: int = 100
    ) -> BrowseResponse:
        """浏览目录"""
        provider = self._get_provider(storage_type)
        
        # 对于夸克根目录，统一使用 "0"
        if storage_type == StorageType.QUARK and (path == "/" or not path):
            path = "0"
            
        items, total, parent_path = await provider.list(path, page, size)
        
        return BrowseResponse(
            items=items,
            total=total,
            path=path,
            parent_path=parent_path
        )

    async def handle_operation(self, request: FileOperationRequest) -> dict:
        """处理统一的文件操作"""
        provider = self._get_provider(request.storage)
        
        if request.action == FileOperationAction.MOVE:
            if not request.target:
                raise HTTPException(status_code=400, detail="Target path is required for move")
            await provider.move_batch(request.paths, request.target)
            return {"status": "success", "action": "move", "count": len(request.paths)}
            
        elif request.action == FileOperationAction.DELETE:
            await provider.delete_batch(request.paths)
            return {"status": "success", "action": "delete", "count": len(request.paths)}
            
        elif request.action == FileOperationAction.RENAME:
            if not request.target:
                 raise HTTPException(status_code=400, detail="New name is required for rename")
            results = []
            for path in request.paths:
                try:
                    res = await provider.rename(path, request.target)
                    results.append({"path": path, "success": True})
                except Exception as e:
                    results.append({"path": path, "success": False, "error": str(e)})
            return {"status": "success", "results": results}
            
        elif request.action == FileOperationAction.MKDIR:
            if not request.target:
                 raise HTTPException(status_code=400, detail="Folder name is required")
            parent = request.paths[0] if request.paths else "0"
            try:
                res = await provider.mkdir(parent, request.target)
                return {"status": "success", "result": res}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
                
        return {"status": "error", "message": "Unknown action"}

async def get_file_manager_service():
    return FileManagerService()
