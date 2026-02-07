"""
媒体重命名API

提供媒体文件重命名功能的RESTful接口:
- 预览重命名
- 执行重命名
- 回滚操作
- 批次管理
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.logging import get_logger
from app.services.rename_service import get_rename_service, RenameService
from app.models.scrape import RenameBatch, RenameHistory
from app.core.validators import validate_path, validate_identifier, InputValidationError
from app.core.dependencies import require_api_key
from app.core.constants import MAX_PATH_LENGTH, MAX_BATCH_SIZE, MIN_BATCH_SIZE, DEFAULT_BATCH_SIZE

logger = get_logger(__name__)
router = APIRouter(prefix="/api/rename", tags=["媒体重命名"])


# ==================== Request/Response Models ====================

class RenameOptions(BaseModel):
    """预览选项"""
    model_config = ConfigDict(extra="forbid")

    recursive: bool = True
    use_ai: bool = False
    create_folders: bool = True
    batch_size: int = Field(DEFAULT_BATCH_SIZE, ge=MIN_BATCH_SIZE, le=MAX_BATCH_SIZE)


class RenamePreviewRequest(BaseModel):
    """预览请求"""
    model_config = ConfigDict(extra="forbid")

    target_path: Optional[str] = Field(default=None, max_length=MAX_PATH_LENGTH)
    path: Optional[str] = Field(default=None, max_length=MAX_PATH_LENGTH)  # 兼容旧版API
    media_type: Literal["auto", "movie", "tv"] = "auto"
    recursive: bool = True  # 兼容旧版API
    options: Optional[RenameOptions] = None

    @field_validator("target_path", "path")
    @classmethod
    def validate_paths(cls, v):
        if v is None:
            return v
        return validate_path(v, "target_path", allow_absolute=True)

    @model_validator(mode="after")
    def validate_target(self):
        if not self.target_path and not self.path:
            raise ValueError("target_path or path is required")
        return self


class RenameItemResponse(BaseModel):
    """单个重命名项"""
    original_path: str
    original_name: str
    new_path: Optional[str] = None
    new_name: Optional[str] = None
    tmdb_id: Optional[int] = None
    title: Optional[str] = None
    year: Optional[int] = None
    confidence: float = 0.0
    status: str
    error_message: Optional[str] = None


class RenamePreviewResponse(BaseModel):
    """预览响应"""
    batch_id: str
    target_path: str
    total_items: int
    matched_items: int
    skipped_items: int
    items: List[RenameItemResponse]
    # 兼容旧版API
    tasks: Optional[List[RenameItemResponse]] = None


class RenameExecuteRequest(BaseModel):
    """执行请求"""
    model_config = ConfigDict(extra="forbid")
    batch_id: str = Field(..., min_length=1, max_length=64)

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, v):
        return validate_identifier(v, "batch_id")


class RenameExecuteResponse(BaseModel):
    """执行响应"""
    batch_id: str
    total_items: int
    success_items: int
    failed_items: int
    skipped_items: int


class RenameBatchResponse(BaseModel):
    """批次信息"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: str
    target_path: str
    media_type: str
    total_items: int
    success_items: int
    failed_items: int
    skipped_items: int
    status: str
    created_at: Any
    completed_at: Any = None


class RenameHistoryResponse(BaseModel):
    """历史记录"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: str
    original_path: str
    original_name: str
    new_path: Optional[str]
    new_name: Optional[str]
    status: str
    tmdb_id: Optional[int]
    confidence: Optional[float]
    error_message: Optional[str]
    created_at: Any
    executed_at: Any = None
    rolled_back_at: Any = None


# ==================== API Endpoints ====================

@router.post("/preview", response_model=RenamePreviewResponse)
async def preview_rename(
    request: RenamePreviewRequest,
    _auth: None = Depends(require_api_key),
    service: RenameService = Depends(get_rename_service)
):
    """
    预览重命名

    分析指定目录下的媒体文件，匹配TMDB信息，生成重命名预览。
    不会实际修改任何文件。
    """
    try:
        # 兼容处理: 支持 target_path 或 path
        target_path = request.target_path or request.path
        if not target_path:
            raise HTTPException(status_code=422, detail="target_path or path is required")

        # 合并options
        options = request.options.model_dump() if request.options else {}
        if "recursive" not in options:
            options["recursive"] = request.recursive

        result = await service.preview(
            target_path=target_path,
            media_type=request.media_type,
            options=options
        )
        
        # 构建items列表
        items_list = [
            RenameItemResponse(
                original_path=item.original_path,
                original_name=item.original_name,
                new_path=item.new_path,
                new_name=item.new_name,
                tmdb_id=item.tmdb_id,
                title=item.title,
                year=item.year,
                confidence=item.confidence,
                status=item.status,
                error_message=item.error_message
            )
            for item in result.items
        ]

        return RenamePreviewResponse(
            batch_id=result.batch_id,
            target_path=result.target_path,
            total_items=result.total_items,
            matched_items=result.matched_items,
            skipped_items=result.skipped_items,
            items=items_list,
            tasks=items_list  # 兼容旧版API
        )
        
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Preview rename failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=RenameExecuteResponse)
async def execute_rename(
    request: RenameExecuteRequest,
    _auth: None = Depends(require_api_key),
    service: RenameService = Depends(get_rename_service)
):
    """
    执行重命名
    
    根据预览生成的batch_id执行实际的文件重命名操作。
    所有操作会被记录，支持后续回滚。
    """
    try:
        result = await service.execute(batch_id=request.batch_id)
        
        return RenameExecuteResponse(
            batch_id=result.batch_id,
            total_items=result.total_items,
            success_items=result.success_items,
            failed_items=result.failed_items,
            skipped_items=result.skipped_items
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Execute rename failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback/{batch_id}", response_model=RenameExecuteResponse)
async def rollback_rename(
    batch_id: str,
    _auth: None = Depends(require_api_key),
    service: RenameService = Depends(get_rename_service)
):
    """
    回滚重命名
    
    将指定批次的所有成功重命名操作回滚到原始状态。
    """
    try:
        batch_id = validate_identifier(batch_id, "batch_id")
        result = await service.rollback(batch_id=batch_id)
        
        return RenameExecuteResponse(
            batch_id=result.batch_id,
            total_items=result.total_items,
            success_items=result.success_items,
            failed_items=result.failed_items,
            skipped_items=result.skipped_items
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batches", response_model=List[RenameBatchResponse])
async def list_batches(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取批次列表"""
    batches = db.query(RenameBatch).order_by(
        RenameBatch.created_at.desc()
    ).offset(skip).limit(limit).all()
    return batches


@router.get("/batches/{batch_id}", response_model=RenameBatchResponse)
async def get_batch(
    batch_id: str,
    db: Session = Depends(get_db)
):
    """获取批次详情"""
    batch_id = validate_identifier(batch_id, "batch_id")
    batch = db.query(RenameBatch).filter(RenameBatch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.get("/batches/{batch_id}/items", response_model=List[RenameHistoryResponse])
async def get_batch_items(
    batch_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """获取批次下的所有项目"""
    batch_id = validate_identifier(batch_id, "batch_id")
    query = db.query(RenameHistory).filter(RenameHistory.batch_id == batch_id)
    
    if status:
        query = query.filter(RenameHistory.status == status)
        
    items = query.order_by(RenameHistory.created_at).offset(skip).limit(limit).all()
    return items


@router.get("/history", response_model=List[RenameHistoryResponse])
async def get_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """获取所有重命名历史"""
    items = db.query(RenameHistory).order_by(
        RenameHistory.created_at.desc()
    ).offset(skip).limit(limit).all()
    return items


@router.get("/status")
async def get_status():
    """获取重命名服务状态"""
    try:
        service = get_rename_service()
        tmdb_available = service._get_tmdb_service() is not None
        return {
            "available": True,
            "rename_service": True,  # BUG-001: 添加缺失字段
            "tmdb_connected": tmdb_available,
            "confidence_threshold": service.confidence_threshold
        }
    except Exception as e:
        return {
            "available": False,
            "rename_service": False,
            "error": str(e)
        }


@router.get("/info")
async def get_info():
    """
    获取重命名服务信息

    BUG-003: 添加缺失的 /api/rename/info 端点
    """
    try:
        service = get_rename_service()
        tmdb_service = service._get_tmdb_service()

        return {
            "service": "rename",
            "version": "1.0.0",
            "available": True,
            "features": {
                "preview": True,
                "execute": True,
                "rollback": True,
                "batch_processing": True
            },
            "config": {
                "confidence_threshold": service.confidence_threshold,
                "tmdb_connected": tmdb_service is not None,
                "templates": list(service.TEMPLATES.keys())
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 添加POST方法支持以兼容测试
@router.post("/info")
async def get_info_post():
    """获取重命名服务信息 (POST兼容)"""
    return await get_info()
