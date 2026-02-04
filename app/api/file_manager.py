from fastapi import APIRouter, Depends, Query, HTTPException
from app.schemas.file_manager import (
    BrowseResponse, StorageType, FileOperationRequest
)
from app.services.file_manager_service import FileManagerService, get_file_manager_service
from app.schemas.base import BaseResponse

router = APIRouter(prefix="/files", tags=["FileManager"])

@router.get("/browse", response_model=BaseResponse[BrowseResponse])
async def browse(
    storage: StorageType = Query(StorageType.QUARK),
    path: str = Query("/", description="目录路径或ID"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    service: FileManagerService = Depends(get_file_manager_service)
):
    """
    浏览文件目录
    """
    try:
        data = await service.browse(storage, path, page, size)
        return BaseResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/operation", response_model=BaseResponse[dict])
async def file_operation(
    request: FileOperationRequest,
    service: FileManagerService = Depends(get_file_manager_service)
):
    """
    统一文件操作 (重命名, 移动, 删除, 创建文件夹)
    """
    try:
        data = await service.handle_operation(request)
        return BaseResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
