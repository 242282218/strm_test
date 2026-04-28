from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.constants import MAX_PATH_LENGTH
from app.core.db import get_db
from app.core.dependencies import require_api_key
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.core.validators import InputValidationError, validate_identifier, validate_path
from app.models.scrape import ScrapeJob
from app.schemas.base import BaseResponse, PageMeta, PageResponse
from app.services.scrape_service import ScrapeService, get_scrape_service


router = APIRouter()


# --- Request Models ---
class ScrapeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force_overwrite: bool = False
    download_images: bool = True
    emby_library_id: str | None = Field(default=None, max_length=128)


class ScrapeJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_path: str = Field(..., max_length=MAX_PATH_LENGTH)
    media_type: Literal["auto", "movie", "tv"] = "auto"
    options: ScrapeOptions | None = None


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
    service: ScrapeService = Depends(get_scrape_service),
):
    """创建刮削任务"""
    try:
        validate_path(request.target_path, "target_path", allow_absolute=True)

        job = await service.create_job(
            target_path=request.target_path,
            media_type=request.media_type,
            options=request.options.model_dump() if request.options else None,
        )
        # 转换为 DTO
        job_dto = ScrapeJobDto.model_validate(job)

        return BaseResponse(data=job_dto, message="Job created successfully")

    except InputValidationError as e:
        raise AppException(
            code=ErrorCode.VALIDATION_INVALID_PARAM,
            message=str(e),
        )
    except Exception as e:
        raise AppException(code=ErrorCode.SYSTEM_INTERNAL_ERROR, message=str(e))


@router.post("/jobs/{job_id}/action/start", response_model=BaseResponse[dict])
async def start_scrape_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
    service: ScrapeService = Depends(get_scrape_service),
):
    """启动刮削任务"""
    try:
        validate_identifier(job_id, "job_id")
        success = await service.start_job(job_id)

        if not success:
            raise AppException(
                code=ErrorCode.REQUEST_NOT_FOUND,
                message=f"Job {job_id} not found or already running",
            )

        return BaseResponse(data={"job_id": job_id}, message="Job started")
    except InputValidationError as e:
        raise AppException(code=ErrorCode.VALIDATION_INVALID_PARAM, message=str(e))


@router.get("/jobs/{job_id}", response_model=BaseResponse[ScrapeJobDto])
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """获取任务详情"""
    try:
        validate_identifier(job_id, "job_id")
        job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
        if not job:
            raise AppException(
                code=ErrorCode.REQUEST_NOT_FOUND,
                message="Job not found",
            )

        job_dto = ScrapeJobDto.model_validate(job)
        return BaseResponse(data=job_dto)
    except InputValidationError as e:
        raise AppException(code=ErrorCode.VALIDATION_INVALID_PARAM, message=str(e))


@router.get("/jobs", response_model=PageResponse[list[ScrapeJobDto]])
async def list_jobs(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """获取任务列表"""
    skip = (page - 1) * size
    total = db.query(ScrapeJob).count()
    jobs = db.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).offset(skip).limit(size).all()

    job_dtos = []
    for job in jobs:
        dto = ScrapeJobDto.model_validate(job)
        job_dtos.append(dto)

    pages = (total + size - 1) // size

    return PageResponse(data=job_dtos, meta=PageMeta(total=total, page=page, size=size, pages=pages))
