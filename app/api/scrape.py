from __future__ import annotations

import os
import uuid
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.constants import MAX_PATH_LENGTH
from app.core.db import SessionLocal, get_db
from app.core.dependencies import require_api_key
from app.core.logging import get_logger
from app.core.validators import InputValidationError, validate_identifier, validate_path
from app.models.scrape import CategoryStrategy, ScrapeJob, ScrapePath, ScrapeRecord
from app.services.cron_service import get_cron_service
from app.services.scrape_service import ScrapeService, get_scrape_service

logger = get_logger(__name__)
router = APIRouter(prefix="/scrape", tags=["scrape"])

_CRON_HANDLER_REGISTERED = False

# 用于防止重复任务启动的锁
_path_job_locks: dict[str, asyncio.Lock] = {}


def _get_path_job_lock(path_id: str) -> asyncio.Lock:
    """获取指定 path_id 的任务启动锁"""
    if path_id not in _path_job_locks:
        _path_job_locks[path_id] = asyncio.Lock()
    return _path_job_locks[path_id]


class ScrapeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: Optional[str] = Field(default=None, max_length=MAX_PATH_LENGTH)
    dest_path: Optional[str] = Field(default=None, max_length=MAX_PATH_LENGTH)
    force_overwrite: bool = False
    generate_nfo: bool = True
    download_images: bool = True
    emby_library_id: Optional[str] = Field(default=None, max_length=128)
    scrape_mode: Literal["only_scrape", "scrape_and_rename", "only_rename"] = "scrape_and_rename"
    rename_mode: Literal["move", "copy", "hardlink", "softlink"] = "move"
    max_threads: int = Field(default=1, ge=1, le=32)


class ScrapeJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_path: str = Field(..., max_length=MAX_PATH_LENGTH)
    media_type: Literal["auto", "movie", "tv"] = "auto"
    options: Optional[ScrapeOptions] = None

    @field_validator("target_path")
    @classmethod
    def validate_target_path(cls, value: str) -> str:
        return validate_path(value, "target_path")


class ScrapeJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    target_path: str
    status: str
    total_items: int
    processed_items: int
    success_items: int
    failed_items: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class ScrapePathCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(..., max_length=MAX_PATH_LENGTH)
    dest_path: str = Field(..., max_length=MAX_PATH_LENGTH)
    media_type: Literal["auto", "movie", "tv"] = "auto"
    scrape_mode: Literal["only_scrape", "scrape_and_rename", "only_rename"] = "scrape_and_rename"
    rename_mode: Literal["move", "copy", "hardlink", "softlink"] = "move"
    max_threads: int = Field(default=1, ge=1, le=32)
    cron: Optional[str] = Field(default=None, max_length=120)
    enabled: bool = True
    enable_secondary_category: bool = True

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        return validate_path(value, "source_path")

    @field_validator("dest_path")
    @classmethod
    def validate_dest_path(cls, value: str) -> str:
        return validate_path(value, "dest_path")

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cron = value.strip()
        if not cron:
            return None
        _validate_cron_expression(cron)
        return cron


class ScrapePathUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: Optional[str] = Field(default=None, max_length=MAX_PATH_LENGTH)
    dest_path: Optional[str] = Field(default=None, max_length=MAX_PATH_LENGTH)
    media_type: Optional[Literal["auto", "movie", "tv"]] = None
    scrape_mode: Optional[Literal["only_scrape", "scrape_and_rename", "only_rename"]] = None
    rename_mode: Optional[Literal["move", "copy", "hardlink", "softlink"]] = None
    max_threads: Optional[int] = Field(default=None, ge=1, le=32)
    cron: Optional[str] = Field(default=None, max_length=120)
    enabled: Optional[bool] = None
    enable_secondary_category: Optional[bool] = None

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return validate_path(value, "source_path")

    @field_validator("dest_path")
    @classmethod
    def validate_dest_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return validate_path(value, "dest_path")

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cron = value.strip()
        if not cron:
            return None
        _validate_cron_expression(cron)
        return cron


class ScrapePathDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    path_id: str
    source_path: str
    dest_path: str
    media_type: str
    scrape_mode: str
    rename_mode: str
    max_threads: int
    cron: Optional[str]
    enabled: bool
    cron_enabled: bool
    enable_secondary_category: bool
    status: str
    last_job_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class ScrapePathListResponse(BaseModel):
    items: List[ScrapePathDto]
    total: int


class ScrapePathActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path_id: str = Field(..., max_length=64)


class ScrapePathToggleCronRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path_id: str = Field(..., max_length=64)
    enabled: Optional[bool] = None


class ScrapeRecordDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_id: str
    job_id: str
    path_id: Optional[str]
    item_id: Optional[int]
    source_file: str
    target_file: Optional[str]
    media_type: Optional[str]
    tmdb_id: Optional[int]
    title: Optional[str]
    year: Optional[int]
    status: str
    error_code: Optional[str]
    error_message: Optional[str]
    recognition_result: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]


class ScrapeRecordListResponse(BaseModel):
    items: List[ScrapeRecordDto]
    total: int


class RecordIdsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_ids: List[str] = Field(default_factory=list)


class CategoryStrategyDto(BaseModel):
    enabled: bool
    anime_keywords: List[str]
    folder_names: Dict[str, str]


class CategoryStrategyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    anime_keywords: List[str] = Field(default_factory=list)
    folder_names: Dict[str, str] = Field(
        default_factory=lambda: {
            "anime": "动漫文件夹",
            "movie": "电影",
            "tv": "电视剧",
        }
    )


class CategoryPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_name: str = Field(..., min_length=1, max_length=255)
    media_type: Literal["auto", "movie", "tv"] = "auto"


class CategoryPreviewResponse(BaseModel):
    category_key: Literal["anime", "movie", "tv"]
    category_folder: str


def _validate_cron_expression(cron: str) -> None:
    fields = cron.split()
    if len(fields) == 5:
        CronTrigger.from_crontab(cron)
        return
    if len(fields) == 6:
        CronTrigger(
            second=fields[0],
            minute=fields[1],
            hour=fields[2],
            day=fields[3],
            month=fields[4],
            day_of_week=fields[5],
        )
        return
    raise ValueError("cron must contain 5 or 6 fields")


def _refresh_path_status(db: Session, path: ScrapePath) -> None:
    if path.status != "running" or not path.last_job_id:
        return
    job = db.query(ScrapeJob).filter(ScrapeJob.job_id == path.last_job_id).first()
    if not job or job.status != "running":
        path.status = "idle"
        db.commit()


def _build_path_options(path: ScrapePath) -> Dict[str, Any]:
    return {
        "path_id": path.path_id,
        "source_path": path.source_path,
        "dest_path": path.dest_path,
        "scrape_mode": path.scrape_mode,
        "rename_mode": path.rename_mode,
        "max_threads": path.max_threads,
        "enable_secondary_category": path.enable_secondary_category,
        "generate_nfo": True,
        "download_images": True,
    }


def _default_category_strategy() -> CategoryStrategyDto:
    return CategoryStrategyDto(
        enabled=True,
        anime_keywords=["anime", "animation", "动漫", "番剧"],
        folder_names={
            "anime": "动漫文件夹",
            "movie": "电影",
            "tv": "电视剧",
        },
    )


def _load_category_strategy(db: Session) -> CategoryStrategyDto:
    row = db.query(CategoryStrategy).order_by(CategoryStrategy.id.asc()).first()
    if not row:
        return _default_category_strategy()

    defaults = _default_category_strategy()
    folder_names = dict(defaults.folder_names)
    if isinstance(row.folder_names, dict):
        folder_names.update({k: str(v) for k, v in row.folder_names.items() if k in {"anime", "movie", "tv"}})
    keywords = row.anime_keywords if isinstance(row.anime_keywords, list) else defaults.anime_keywords
    return CategoryStrategyDto(
        enabled=bool(row.enabled),
        anime_keywords=[str(keyword) for keyword in keywords],
        folder_names=folder_names,
    )


def _classify_file_name(
    file_name: str,
    media_type: Literal["auto", "movie", "tv"],
    strategy: CategoryStrategyDto,
) -> Literal["anime", "movie", "tv"]:
    lowered = file_name.lower()
    for keyword in strategy.anime_keywords:
        if keyword and str(keyword).lower() in lowered:
            return "anime"
    if media_type == "movie":
        return "movie"
    if media_type == "tv":
        return "tv"
    if "s01e" in lowered or "season" in lowered:
        return "tv"
    return "movie"


async def _start_path_job(path_id: str) -> Dict[str, Any]:
    """启动路径刮削任务，使用锁防止竞态条件"""
    # 获取该 path_id 的专用锁
    lock = _get_path_job_lock(path_id)
    
    # 使用锁确保同一时间只有一个请求在检查状态和启动任务
    async with lock:
        db = SessionLocal()
        try:
            path = db.query(ScrapePath).filter(ScrapePath.path_id == path_id).first()
            if not path:
                return {"ok": False, "reason": "not_found"}
            _refresh_path_status(db, path)

            # 双重检查：获取锁后再次确认状态
            if path.status == "running" and path.last_job_id:
                running_job = db.query(ScrapeJob).filter(ScrapeJob.job_id == path.last_job_id).first()
                if running_job and running_job.status == "running":
                    return {
                        "ok": True,
                        "started": False,
                        "already_running": True,
                        "job_id": running_job.job_id,
                        "path_id": path.path_id,
                    }

            service = get_scrape_service()
            job = await service.create_job(
                target_path=path.source_path,
                media_type=path.media_type,
                options=_build_path_options(path),
            )
            started = await service.start_job(job.job_id)
            if not started:
                return {"ok": False, "reason": "start_failed"}

            path.last_job_id = job.job_id
            path.status = "running"
            db.commit()
            return {
                "ok": True,
                "started": True,
                "already_running": False,
                "job_id": job.job_id,
                "path_id": path.path_id,
            }
        finally:
            db.close()


def _ensure_scrape_path_cron_handler_registered() -> None:
    global _CRON_HANDLER_REGISTERED
    if _CRON_HANDLER_REGISTERED:
        return

    cron_service = get_cron_service()

    async def _handler(path_id: str, **_kwargs):
        result = await _start_path_job(path_id)
        if not result.get("ok"):
            logger.warning("scrape path cron trigger failed: %s", result)

    cron_service.register_handler("scrape_path_start", _handler)
    _CRON_HANDLER_REGISTERED = True


@router.post("/jobs", response_model=ScrapeJobResponse)
async def create_scrape_job(
    request: ScrapeJobCreateRequest,
    _auth: None = Depends(require_api_key),
    service: ScrapeService = Depends(get_scrape_service),
):
    try:
        job = await service.create_job(
            target_path=request.target_path,
            media_type=request.media_type,
            options=request.options.model_dump() if request.options else None,
        )
        return job
    except InputValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("failed to create scrape job")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/start")
async def start_scrape_job(
    job_id: str,
    _auth: None = Depends(require_api_key),
    service: ScrapeService = Depends(get_scrape_service),
):
    job_id = validate_identifier(job_id, "job_id")
    started = await service.start_job(job_id)
    if not started:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, "started": True}


@router.get("/jobs/{job_id}", response_model=ScrapeJobResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job_id = validate_identifier(job_id, "job_id")
    job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/jobs", response_model=List[ScrapeJobResponse])
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(ScrapeJob)
        .order_by(ScrapeJob.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return jobs


@router.get("/paths", response_model=ScrapePathListResponse)
@router.get("/pathes", response_model=ScrapePathListResponse, include_in_schema=False)  # 保留旧路由以兼容
async def list_scrape_paths(
    keyword: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    enabled: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(ScrapePath)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                ScrapePath.source_path.ilike(like),
                ScrapePath.dest_path.ilike(like),
                ScrapePath.path_id.ilike(like),
            )
        )
    if status:
        query = query.filter(ScrapePath.status == status)
    if enabled is not None:
        query = query.filter(ScrapePath.enabled == enabled)

    total = query.count()
    items = (
        query.order_by(ScrapePath.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    for path in items:
        _refresh_path_status(db, path)
    return ScrapePathListResponse(items=items, total=total)


@router.post("/paths", response_model=ScrapePathDto)
@router.post("/pathes", response_model=ScrapePathDto, include_in_schema=False)  # 保留旧路由以兼容
async def create_scrape_path(
    request: ScrapePathCreateRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    path = ScrapePath(
        path_id=str(uuid.uuid4()),
        source_path=request.source_path,
        dest_path=request.dest_path,
        media_type=request.media_type,
        scrape_mode=request.scrape_mode,
        rename_mode=request.rename_mode,
        max_threads=request.max_threads,
        cron=request.cron,
        enabled=request.enabled,
        cron_enabled=False,
        enable_secondary_category=request.enable_secondary_category,
        status="idle",
    )
    db.add(path)
    db.commit()
    db.refresh(path)
    return path


@router.get("/paths/{path_id}", response_model=ScrapePathDto)
@router.get("/pathes/{path_id}", response_model=ScrapePathDto, include_in_schema=False)  # 保留旧路由以兼容
async def get_scrape_path(path_id: str, db: Session = Depends(get_db)):
    path = db.query(ScrapePath).filter(ScrapePath.path_id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="scrape path not found")
    _refresh_path_status(db, path)
    return path


@router.put("/paths/{path_id}", response_model=ScrapePathDto)
@router.put("/pathes/{path_id}", response_model=ScrapePathDto, include_in_schema=False)  # 保留旧路由以兼容
async def update_scrape_path(
    path_id: str,
    request: ScrapePathUpdateRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    path = db.query(ScrapePath).filter(ScrapePath.path_id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="scrape path not found")

    updates = request.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(path, field_name, value)
    path.updated_at = datetime.now()
    db.commit()
    db.refresh(path)
    return path


@router.delete("/paths/{path_id}")
@router.delete("/pathes/{path_id}", include_in_schema=False)  # 保留旧路由以兼容
async def delete_scrape_path(
    path_id: str,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    path = db.query(ScrapePath).filter(ScrapePath.path_id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="scrape path not found")

    cron_service = get_cron_service()
    cron_service.remove_job(f"scrape_path_{path.path_id}")

    db.delete(path)
    db.commit()
    return {"deleted": True, "path_id": path_id}


@router.post("/paths/start")
@router.post("/pathes/start", include_in_schema=False)  # 保留旧路由以兼容
async def start_scrape_path(
    body: ScrapePathActionRequest,
    _auth: None = Depends(require_api_key),
):
    result = await _start_path_job(body.path_id)
    if not result.get("ok"):
        if result.get("reason") == "not_found":
            raise HTTPException(status_code=404, detail="scrape path not found")
        raise HTTPException(status_code=500, detail="failed to start scrape path")
    return result


@router.post("/paths/stop")
@router.post("/pathes/stop", include_in_schema=False)  # 保留旧路由以兼容
async def stop_scrape_path(
    body: ScrapePathActionRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    path = db.query(ScrapePath).filter(ScrapePath.path_id == body.path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="scrape path not found")

    stopped = False
    if path.last_job_id:
        stopped = await get_scrape_service().stop_job(path.last_job_id)

    path.status = "stopped"
    db.commit()
    return {
        "path_id": path.path_id,
        "stopped": True if stopped or not path.last_job_id else stopped,
        "job_id": path.last_job_id,
    }


@router.post("/paths/toggle-cron")
@router.post("/pathes/toggle-cron", include_in_schema=False)  # 保留旧路由以兼容
async def toggle_scrape_path_cron(
    body: ScrapePathToggleCronRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    path = db.query(ScrapePath).filter(ScrapePath.path_id == body.path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="scrape path not found")

    target_enabled = (not path.cron_enabled) if body.enabled is None else bool(body.enabled)

    cron_service = get_cron_service()
    cron_job_id = f"scrape_path_{path.path_id}"

    if target_enabled:
        if not path.cron:
            raise HTTPException(status_code=400, detail="cron expression is required")
        _validate_cron_expression(path.cron)
        _ensure_scrape_path_cron_handler_registered()
        if cron_service.get_job(cron_job_id):
            cron_service.remove_job(cron_job_id)
        cron_service.add_cron_job(
            job_id=cron_job_id,
            cron_expression=path.cron,
            task_type="scrape_path_start",
            path_id=path.path_id,
        )
    else:
        cron_service.remove_job(cron_job_id)

    path.cron_enabled = target_enabled
    db.commit()
    return {"path_id": path.path_id, "cron_enabled": path.cron_enabled}


@router.get("/category-strategy", response_model=CategoryStrategyDto)
async def get_category_strategy(db: Session = Depends(get_db)):
    return _load_category_strategy(db)


@router.put("/category-strategy", response_model=CategoryStrategyDto)
async def update_category_strategy(
    body: CategoryStrategyUpdateRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    row = db.query(CategoryStrategy).order_by(CategoryStrategy.id.asc()).first()
    if not row:
        row = CategoryStrategy()
        db.add(row)

    folder_names = _default_category_strategy().folder_names
    folder_names.update({k: v for k, v in body.folder_names.items() if k in {"anime", "movie", "tv"}})

    row.enabled = body.enabled
    row.anime_keywords = [str(keyword).strip() for keyword in body.anime_keywords if str(keyword).strip()]
    row.folder_names = folder_names
    row.updated_at = datetime.now()
    db.commit()
    return _load_category_strategy(db)


@router.post("/category-strategy/preview", response_model=CategoryPreviewResponse)
async def preview_category_strategy(
    body: CategoryPreviewRequest,
    db: Session = Depends(get_db),
):
    strategy = _load_category_strategy(db)
    category_key = _classify_file_name(body.file_name, body.media_type, strategy)
    return CategoryPreviewResponse(
        category_key=category_key,
        category_folder=strategy.folder_names[category_key],
    )


@router.get("/records", response_model=ScrapeRecordListResponse)
async def list_scrape_records(
    keyword: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(ScrapeRecord)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                ScrapeRecord.source_file.ilike(like),
                ScrapeRecord.target_file.ilike(like),
                ScrapeRecord.title.ilike(like),
                ScrapeRecord.error_message.ilike(like),
                ScrapeRecord.error_code.ilike(like),
            )
        )
    if status:
        query = query.filter(ScrapeRecord.status == status)

    total = query.count()
    items = (
        query.order_by(ScrapeRecord.updated_at.desc(), ScrapeRecord.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return ScrapeRecordListResponse(items=items, total=total)


@router.get("/records/{record_id}", response_model=ScrapeRecordDto)
async def get_scrape_record(record_id: str, db: Session = Depends(get_db)):
    record = db.query(ScrapeRecord).filter(ScrapeRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="scrape record not found")
    return record


@router.post("/re-scrape")
async def re_scrape_records(
    body: RecordIdsRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    if not body.record_ids:
        return {"requested": 0, "updated": 0, "queued_jobs": 0}

    records = db.query(ScrapeRecord).filter(ScrapeRecord.record_id.in_(body.record_ids)).all()
    updated = 0
    path_ids: set[str] = set()
    source_dirs: set[str] = set()

    for record in records:
        record.status = "pending"
        record.error_code = None
        record.error_message = None
        record.updated_at = datetime.now()
        updated += 1
        if record.path_id:
            path_ids.add(record.path_id)
        else:
            source_dirs.add(str(record.source_file))
    db.commit()

    queued_jobs = 0
    for path_id in sorted(path_ids):
        result = await _start_path_job(path_id)
        if result.get("ok"):
            queued_jobs += 1

    service = get_scrape_service()
    for source in sorted(source_dirs):
        source_dir = source if os.path.isdir(source) else os.path.dirname(source)
        if not source_dir:
            continue
        try:
            job = await service.create_job(
                target_path=source_dir,
                options={"source_path": source_dir, "dest_path": source_dir},
            )
            if await service.start_job(job.job_id):
                queued_jobs += 1
        except Exception:
            logger.warning("failed to queue re-scrape for source: %s", source_dir)

    return {"requested": len(body.record_ids), "updated": updated, "queued_jobs": queued_jobs}


class ClearRecordsRequest(BaseModel):
    """清理记录请求"""
    model_config = ConfigDict(extra="forbid")
    confirm: bool = Field(
        default=False,
        description="必须设置为 true 以确认删除操作"
    )


@router.post("/clear-failed")
async def clear_failed_records(
    body: ClearRecordsRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """清理失败的刮削记录
    
    需要设置 confirm=true 来确认删除操作
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Missing confirmation. Set confirm=true to proceed with deletion."
        )
    
    failed_query = db.query(ScrapeRecord).filter(
        ScrapeRecord.status.in_(["scrape_failed", "rename_failed"])
    )
    count = failed_query.count()
    failed_query.delete(synchronize_session=False)
    db.commit()
    logger.info("Cleared %d failed scrape records", count)
    return {"cleared": count}


class TruncateRecordsRequest(BaseModel):
    """清空记录请求"""
    model_config = ConfigDict(extra="forbid")
    confirm: bool = Field(
        default=False,
        description="必须设置为 true 以确认删除操作"
    )


@router.post("/truncate-all")
async def truncate_all_records(
    body: TruncateRecordsRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """清空所有刮削记录
    
    危险操作！需要设置 confirm=true 来确认删除操作
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Missing confirmation. Set confirm=true to proceed with deletion. This is a destructive operation!"
        )
    
    count = db.query(ScrapeRecord).count()
    db.query(ScrapeRecord).delete(synchronize_session=False)
    db.commit()
    logger.warning("Truncated all %d scrape records", count)
    return {"truncated": count}
