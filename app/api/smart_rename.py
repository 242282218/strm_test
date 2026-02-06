"""
智能重命名 API

提供增强的媒体文件重命名功能:
- 多算法选择 (标准/AI增强/纯AI)
- Emby 规范命名
- 命名规则自定义
- 批量处理与预览
- 回滚支持
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.validators import validate_path, validate_identifier, InputValidationError
from app.core.dependencies import require_api_key
from app.models.scrape import RenameBatch, RenameHistory
from app.services.smart_rename_service import (
    get_smart_rename_service,
    SmartRenameService,
    SmartRenameOptions,
    AlgorithmType,
    NamingStandard,
    NamingConfig
)
from app.services.ai_connectivity_service import get_ai_connectivity_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/smart-rename", tags=["智能重命名"])


# ==================== Request/Response Models ====================

class NamingConfigRequest(BaseModel):
    """命名配置请求"""
    model_config = ConfigDict(extra="forbid")
    
    movie_template: str = "{title} ({year})"
    tv_episode_template: str = "{title} - S{season:02d}E{episode:02d}"
    specials_folder: str = "Season 00"
    include_quality: bool = False
    include_source: bool = False
    include_codec: bool = False
    include_tmdb_id: bool = False
    sanitize_filenames: bool = True


class SmartRenamePreviewRequest(BaseModel):
    """智能重命名预览请求"""
    model_config = ConfigDict(extra="forbid")
    
    target_path: str = Field(..., max_length=500)
    algorithm: Literal["standard", "ai_enhanced", "ai_only"] = "ai_enhanced"
    naming_standard: Literal["emby", "plex", "kodi", "custom"] = "emby"
    recursive: bool = True
    create_folders: bool = True
    auto_confirm_high_confidence: bool = True
    high_confidence_threshold: float = Field(0.9, ge=0.0, le=1.0)
    ai_confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    force_ai_parse: bool = False
    naming_config: Optional[NamingConfigRequest] = None
    
    @field_validator("target_path")
    @classmethod
    def validate_target_path(cls, v):
        return validate_path(v, "target_path")


class SmartRenameItemResponse(BaseModel):
    """智能重命名项目响应"""
    original_path: str
    original_name: str
    new_path: Optional[str] = None
    new_name: Optional[str] = None
    media_type: str = "unknown"
    tmdb_id: Optional[int] = None
    tmdb_title: Optional[str] = None
    tmdb_year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    overall_confidence: float = 0.0
    status: str = "pending"
    needs_confirmation: bool = False
    confirmation_reason: Optional[str] = None
    used_algorithm: Optional[str] = None


class SmartRenamePreviewResponse(BaseModel):
    """智能重命名预览响应"""
    batch_id: str
    target_path: str
    total_items: int
    parsed_items: int
    matched_items: int
    skipped_items: int
    needs_confirmation: int
    items: List[SmartRenameItemResponse]
    algorithm_used: str
    naming_standard: str


class SmartRenameExecuteRequest(BaseModel):
    """智能重命名执行请求"""
    model_config = ConfigDict(extra="forbid")
    batch_id: str = Field(..., min_length=1, max_length=64)
    operations: Optional[List[Dict[str, str]]] = None
    
    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, v):
        return validate_identifier(v, "batch_id")

    @field_validator("operations")
    @classmethod
    def validate_operations(cls, v):
        if v is None:
            return v

        validated: List[Dict[str, str]] = []
        for op in v:
            original_path = validate_path((op or {}).get("original_path", ""), "original_path")
            new_name = ((op or {}).get("new_name", "") or "").strip()
            if not new_name:
                raise InputValidationError("new_name is required")
            validated.append(
                {
                    "original_path": original_path,
                    "new_name": new_name,
                }
            )
        return validated


class SmartRenameExecuteResponse(BaseModel):
    """智能重命名执行响应"""
    batch_id: str
    total_items: int
    success_items: int
    failed_items: int
    skipped_items: int


class AlgorithmInfoResponse(BaseModel):
    """算法信息响应"""
    algorithm: str
    name: str
    description: str
    features: List[str]
    recommended: bool = False


class NamingStandardInfoResponse(BaseModel):
    """命名标准信息响应"""
    standard: str
    name: str
    description: str
    movie_example: str
    tv_example: str
    specials_example: str


class ValidationResponse(BaseModel):
    """命名验证响应"""
    filename: str
    is_valid: bool
    suggestions: List[str]
    warnings: List[str]


class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(..., min_length=1, max_length=500)


# ==================== API Endpoints ====================

@router.post("/preview", response_model=SmartRenamePreviewResponse)
async def smart_preview(
    request: SmartRenamePreviewRequest,
    _auth: None = Depends(require_api_key),
    service: SmartRenameService = Depends(get_smart_rename_service)
):
    """
    智能重命名预览
    
    分析指定目录下的媒体文件，使用选择的算法和命名标准生成重命名预览。
    不会实际修改任何文件。
    """
    try:
        # 构建命名配置
        naming_config = NamingConfig()
        if request.naming_config:
            naming_config.movie_template = request.naming_config.movie_template
            naming_config.tv_episode_template = request.naming_config.tv_episode_template
            naming_config.specials_folder = request.naming_config.specials_folder
            naming_config.include_quality = request.naming_config.include_quality
            naming_config.include_source = request.naming_config.include_source
            naming_config.include_codec = request.naming_config.include_codec
            naming_config.include_tmdb_id = request.naming_config.include_tmdb_id
            naming_config.sanitize_filenames = request.naming_config.sanitize_filenames
        
        # 构建选项
        options = SmartRenameOptions(
            algorithm=AlgorithmType(request.algorithm),
            naming_standard=NamingStandard(request.naming_standard),
            naming_config=naming_config,
            recursive=request.recursive,
            create_folders=request.create_folders,
            auto_confirm_high_confidence=request.auto_confirm_high_confidence,
            high_confidence_threshold=request.high_confidence_threshold,
            ai_confidence_threshold=request.ai_confidence_threshold,
            force_ai_parse=request.force_ai_parse
        )
        
        # 执行预览
        result = await service.preview(
            target_path=request.target_path,
            options=options
        )
        
        # 构建响应
        items_list = [
            SmartRenameItemResponse(
                original_path=item.original_path,
                original_name=item.original_name,
                new_path=item.new_path,
                new_name=item.new_name,
                media_type=item.media_type,
                tmdb_id=item.tmdb_id,
                tmdb_title=item.tmdb_title,
                tmdb_year=item.tmdb_year,
                season=item.season,
                episode=item.episode,
                overall_confidence=item.overall_confidence,
                status=item.status,
                needs_confirmation=item.needs_confirmation,
                confirmation_reason=item.confirmation_reason,
                used_algorithm=item.used_algorithm
            )
            for item in result.items
        ]
        
        return SmartRenamePreviewResponse(
            batch_id=result.batch_id,
            target_path=result.target_path,
            total_items=result.total_items,
            parsed_items=result.parsed_items,
            matched_items=result.matched_items,
            skipped_items=result.skipped_items,
            needs_confirmation=result.needs_confirmation,
            items=items_list,
            algorithm_used=result.algorithm_used,
            naming_standard=result.naming_standard
        )
        
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Smart preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=SmartRenameExecuteResponse)
async def smart_execute(
    request: SmartRenameExecuteRequest,
    _auth: None = Depends(require_api_key),
    service: SmartRenameService = Depends(get_smart_rename_service)
):
    """
    执行智能重命名
    
    根据预览生成的 batch_id 执行实际的文件重命名操作。
    所有操作会被记录，支持后续回滚。
    """
    try:
        result = await service.execute(
            batch_id=request.batch_id,
            operations=request.operations
        )
        
        return SmartRenameExecuteResponse(
            batch_id=result["batch_id"],
            total_items=result["total_items"],
            success_items=result["success_items"],
            failed_items=result["failed_items"],
            skipped_items=result["skipped_items"]
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Smart execute failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback/{batch_id}", response_model=SmartRenameExecuteResponse)
async def smart_rollback(
    batch_id: str,
    _auth: None = Depends(require_api_key),
    service: SmartRenameService = Depends(get_smart_rename_service)
):
    """
    回滚智能重命名
    
    将指定批次的所有成功重命名操作回滚到原始状态。
    """
    try:
        batch_id = validate_identifier(batch_id, "batch_id")
        result = await service.rollback(batch_id=batch_id)
        
        return SmartRenameExecuteResponse(
            batch_id=result["batch_id"],
            total_items=result["total_items"],
            success_items=result["success_items"],
            failed_items=result["failed_items"],
            skipped_items=0
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Smart rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/algorithms", response_model=List[AlgorithmInfoResponse])
async def list_algorithms():
    """
    获取可用算法列表
    
    返回所有支持的重命名算法及其说明。
    """
    return [
        AlgorithmInfoResponse(
            algorithm="standard",
            name="标准本地算法",
            description="使用正则表达式解析文件名，速度快但准确性取决于文件名质量",
            features=["正则解析", "TMDB匹配", "无需API密钥", "离线可用"],
            recommended=False
        ),
        AlgorithmInfoResponse(
            algorithm="ai_enhanced",
            name="AI 增强算法",
            description="先使用正则解析，置信度低时自动调用 AI 解析，平衡速度与准确性",
            features=["智能回退", "AI增强", "TMDB匹配", "置信度评估"],
            recommended=True
        ),
        AlgorithmInfoResponse(
            algorithm="ai_only",
            name="纯 AI 算法",
            description="完全依赖 AI 解析文件名，准确性最高但速度较慢",
            features=["AI解析", "自然语言理解", "TMDB匹配", "最高准确性"],
            recommended=False
        )
    ]


@router.get("/naming-standards", response_model=List[NamingStandardInfoResponse])
async def list_naming_standards():
    """
    获取可用命名标准列表
    
    返回所有支持的媒体服务器命名标准及其示例。
    """
    return [
        NamingStandardInfoResponse(
            standard="emby",
            name="Emby 标准",
            description="符合 Emby 媒体服务器的命名规范，兼容性最佳",
            movie_example="Movie Name (2023)/Movie Name (2023).mp4",
            tv_example="Show Name (2023)/Season 01/Show Name - S01E01.mp4",
            specials_example="Show Name (2023)/Season 00/Show Name - S00E01.mp4"
        ),
        NamingStandardInfoResponse(
            standard="plex",
            name="Plex 标准",
            description="符合 Plex 媒体服务器的命名规范",
            movie_example="Movie Name (2023).mp4",
            tv_example="Show Name/Season 01/Show Name - s01e01.mp4",
            specials_example="Show Name/Season 00/Show Name - s00e01.mp4"
        ),
        NamingStandardInfoResponse(
            standard="kodi",
            name="Kodi 标准",
            description="符合 Kodi 媒体中心的命名规范",
            movie_example="Movie Name (2023).mp4",
            tv_example="Show Name/Season 1/Show Name - 1x01.mp4",
            specials_example="Show Name/Specials/Show Name - S00E01.mp4"
        ),
        NamingStandardInfoResponse(
            standard="custom",
            name="自定义",
            description="使用自定义命名模板",
            movie_example="自定义模板",
            tv_example="自定义模板",
            specials_example="自定义模板"
        )
    ]


@router.post("/validate")
async def validate_filename(
    request: Optional[ValidationRequest] = Body(default=None),
    filename: Optional[str] = Query(default=None)
) -> ValidationResponse:
    """
    验证文件名是否符合 Emby 命名规范
    
    检查文件名并提供改进建议。
    """
    from app.services.emby_naming_service import get_emby_naming_service
    
    final_filename = filename
    if request and request.filename:
        final_filename = request.filename
    if not final_filename:
        raise HTTPException(status_code=400, detail="filename is required")

    service = get_emby_naming_service()
    result = service.validate_emby_naming(final_filename)
    
    return ValidationResponse(
        filename=final_filename,
        is_valid=result["is_valid"],
        suggestions=result["suggestions"],
        warnings=result["warnings"]
    )


@router.get("/batches", response_model=List[Dict[str, Any]])
async def list_batches(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取重命名批次列表"""
    batches = db.query(RenameBatch).order_by(
        RenameBatch.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return [
        {
            "id": batch.id,
            "batch_id": batch.batch_id,
            "target_path": batch.target_path,
            "media_type": batch.media_type,
            "total_items": batch.total_items,
            "success_items": batch.success_items,
            "failed_items": batch.failed_items,
            "status": batch.status,
            "created_at": batch.created_at,
            "completed_at": batch.completed_at
        }
        for batch in batches
    ]


@router.get("/batches/{batch_id}/items")
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
    
    return [
        {
            "id": item.id,
            "original_path": item.original_path,
            "original_name": item.original_name,
            "new_path": item.new_path,
            "new_name": item.new_name,
            "status": item.status,
            "tmdb_id": item.tmdb_id,
            "confidence": item.confidence,
            "error_message": item.error_message,
            "created_at": item.created_at,
            "executed_at": item.executed_at
        }
        for item in items
    ]


@router.get("/status")
async def get_smart_rename_status():
    """
    获取智能重命名服务状态
    
    返回服务可用性和配置信息。
    """
    try:
        service = get_smart_rename_service()
        tmdb_available = service._get_tmdb_service() is not None
        
        from app.services.ai_parser_service import get_ai_parser_service
        ai_service = get_ai_parser_service()
        ai_available = ai_service.api_key is not None and len(ai_service.api_key) > 0
        
        return {
            "available": True,
            "smart_rename_service": True,
            "tmdb_connected": tmdb_available,
            "ai_available": ai_available,
            "algorithms": ["standard", "ai_enhanced", "ai_only"],
            "naming_standards": ["emby", "plex", "kodi", "custom"]
        }
    except Exception as e:
        return {
            "available": False,
            "smart_rename_service": False,
            "error": str(e)
        }


@router.get("/ai-connectivity")
async def test_smart_rename_ai_connectivity(
    timeout_seconds: int = Query(8, ge=1, le=30),
    _auth: None = Depends(require_api_key),
):
    """
    Test AI provider connectivity for smart rename (local interface).
    Always tests kimi, deepseek and glm.
    """
    service = get_ai_connectivity_service()
    results = await service.test_providers(
        providers=("kimi", "deepseek", "glm"),
        timeout_seconds=timeout_seconds,
    )
    return {
        "success": True,
        "interface": "smart_rename",
        "all_connected": all(item.get("connected") for item in results),
        "providers": results,
    }
