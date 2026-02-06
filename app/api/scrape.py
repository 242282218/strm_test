from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.logging import get_logger
from app.services.scrape_service import get_scrape_service, ScrapeService
from app.models.scrape import ScrapeJob
from app.core.validators import validate_path, validate_identifier, InputValidationError
from app.core.dependencies import require_api_key
from app.core.constants import MAX_PATH_LENGTH

logger = get_logger(__name__)
router = APIRouter(prefix="/api/scrape", tags=["刮削服务"])

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

    @field_validator("target_path")
    @classmethod
    def validate_target_path(cls, v):
        return validate_path(v, "target_path")

class ScrapeJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    target_path: str
    status: str
    total_items: int = 0
    processed_items: int = 0
    success_items: int = 0
    failed_items: int = 0
    created_at: Any

@router.post("/jobs", response_model=ScrapeJobResponse)
async def create_scrape_job(
    request: ScrapeJobCreateRequest,
    _auth: None = Depends(require_api_key),
    service: ScrapeService = Depends(get_scrape_service)
):
    """创建刮削任务"""
    try:
        job = await service.create_job(
            target_path=request.target_path,
            media_type=request.media_type,
            options=request.options.model_dump() if request.options else None
        )
        return job
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to create scrape job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/start")
async def start_scrape_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
    service: ScrapeService = Depends(get_scrape_service)
):
    """启动刮削任务"""
    job_id = validate_identifier(job_id, "job_id")
    # Start immediately (the service method handles async execution via create_task, 
    # but strictly speaking we can call it directly here if it's non-blocking or returns quickly)
    
    # Actually service.start_job launches a background task.
    success = await service.start_job(job_id)
    if not success:
         raise HTTPException(status_code=400, detail="Failed to start job (not found or already running)")
    
    return {"message": "Job started", "job_id": job_id}

@router.get("/jobs/{job_id}", response_model=ScrapeJobResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """获取任务状态"""
    job_id = validate_identifier(job_id, "job_id")
    job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/jobs", response_model=List[ScrapeJobResponse])
async def list_jobs(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    jobs = db.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).offset(skip).limit(limit).all()
    return jobs
