from fastapi import APIRouter, Depends, Query, BackgroundTasks
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.scrape_service import get_scrape_service, ScrapeService
from app.models.scrape import ScrapeJob
from app.schemas.base import BaseResponse, PageResponse, PageMeta
from app.core.exceptions import AppException, AppErrorCode
from app.core.validators import validate_path, validate_identifier, InputValidationError
from app.core.dependencies import require_api_key
from app.core.constants import MAX_PATH_LENGTH

router = APIRouter()

# --- Request Models ---
class ScrapeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force_overwrite: bool = False
    download_images: bool = True
    emby_library_id: Optional[str] = Field(default=None, max_length=128)

class ScrapeJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_path: str = Field(..., max_length=MAX_PATH_LENGTH)
    media_type: Literal["auto", "movie", "tv"] = "auto"
    options: Optional[ScrapeOptions] = None

# --- Response Models ---
class ScrapeJobDto(BaseModel):
    id: int
    job_id: str
    target_path: str
    status: str
    total_items: int = 0
    processed_items: int = 0
    success_items: int = 0
    failed_items: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Endpoints ---
@router.post("/jobs", response_model=BaseResponse[ScrapeJobDto])
async def create_scrape_job(
    request: ScrapeJobCreateRequest,
    _auth: None = Depends(require_api_key),
    service: ScrapeService = Depends(get_scrape_service)
):
    """创建刮削任务"""
    try:
        validate_path(request.target_path, "target_path")
        
        job = await service.create_job(
            target_path=request.target_path,
            media_type=request.media_type,
            options=request.options.model_dump() if request.options else None
        )
        # 转换为 DTO
        job_dto = ScrapeJobDto.model_validate(job)
        
        return BaseResponse(data=job_dto, message="Job created successfully")
        
    except InputValidationError as e:
        raise AppException(
            code=AppErrorCode.VALIDATION_ERROR,
            message=str(e),
            status_code=422
        )
    except Exception as e:
        raise AppException(
            code=AppErrorCode.SYSTEM_ERROR,
            message=str(e)
        )

@router.post("/jobs/{job_id}/action/start", response_model=BaseResponse[dict])
async def start_scrape_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
    service: ScrapeService = Depends(get_scrape_service)
):
    """启动刮削任务"""
    try:
        validate_identifier(job_id, "job_id")
        success = await service.start_job(job_id)
        
        if not success:
            raise AppException(
                code=AppErrorCode.RESOURCE_NOT_FOUND,
                message=f"Job {job_id} not found or already running",
                status_code=404
            )
            
        return BaseResponse(data={"job_id": job_id}, message="Job started")
    except InputValidationError as e:
         raise AppException(code=AppErrorCode.VALIDATION_ERROR, message=str(e), status_code=422)

@router.get("/jobs/{job_id}", response_model=BaseResponse[ScrapeJobDto])
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """获取任务详情"""
    try:
        validate_identifier(job_id, "job_id")
        job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
        if not job:
            raise AppException(
                code=AppErrorCode.RESOURCE_NOT_FOUND,
                message="Job not found",
                status_code=404
            )
            
        job_dto = ScrapeJobDto.model_validate(job)
        return BaseResponse(data=job_dto)
    except InputValidationError as e:
        raise AppException(code=AppErrorCode.VALIDATION_ERROR, message=str(e), status_code=422)

@router.get("/jobs", response_model=PageResponse[List[ScrapeJobDto]])
async def list_jobs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    skip = (page - 1) * size
    total = db.query(ScrapeJob).count()
    jobs = db.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).offset(skip).limit(size).all()
    
    job_dtos = []
    for job in jobs:
        dto = ScrapeJobDto.model_validate(job)
        job_dtos.append(dto)
        
    pages = (total + size - 1) // size
    
    return PageResponse(
        data=job_dtos,
        meta=PageMeta(total=total, page=page, size=size, pages=pages)
    )
