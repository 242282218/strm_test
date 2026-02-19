"""
Emby API 路由

说明：
- 保留原有连接/刷新/同步/反代相关接口
- 新增事件日志查询、Episode 事件聚合、删除计划 dry-run 与执行保护
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services.config_service import get_config
from app.core.db import get_db
from app.core.dependencies import require_api_key
from app.core.logging import get_logger
from app.core.metrics_collector import MetricsCollector, get_metrics_collector
from app.core.validators import (
    InputValidationError,
    validate_http_url,
    validate_identifier,
    validate_proxy_path,
)
from app.models.emby import EmbyDeletePlan, EmbyEventLog, EmbyMediaItem
from app.services.config_service import get_config_service
from app.services.emby_proxy_service import EmbyProxyService
from app.services.emby_service import get_emby_service
from app.services.proxy_service import ProxyService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/emby", tags=["Emby服务"])

config = get_config()
config_service = get_config_service()


class EmbyConfigUpdate(BaseModel):
    """Emby 配置更新"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    url: str = Field("", max_length=2048)
    api_key: str = Field("", max_length=2048)
    timeout: int = Field(30, ge=1, le=300)
    notify_on_complete: bool = True

    on_strm_generate: bool = True
    on_rename: bool = True
    cron: Optional[str] = None
    library_ids: List[str] = Field(default_factory=list)
    episode_aggregate_window_seconds: int = Field(10, ge=1, le=300)
    delete_execute_enabled: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = (v or "").strip()
        if v:
            validate_http_url(v, "emby.url")
        return v

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cron = v.strip()
        if not cron:
            return None
        fields = cron.split()
        if len(fields) == 5:
            CronTrigger.from_crontab(cron)
            return cron
        if len(fields) == 6:
            CronTrigger(
                second=fields[0],
                minute=fields[1],
                hour=fields[2],
                day=fields[3],
                month=fields[4],
                day_of_week=fields[5],
            )
            return cron
        raise ValueError("cron must have 5 or 6 fields")


class EmbyTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: Optional[int] = Field(5, ge=1, le=300)


class EmbyRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library_ids: Optional[List[str]] = None


class EmbyEventLogDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    event_type: str
    item_id: Optional[str]
    item_name: Optional[str]
    item_type: Optional[str]
    aggregated_count: int
    payload: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class EmbyEventListResponse(BaseModel):
    items: List[EmbyEventLogDto]
    total: int


class EmbyDeletePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(default="manual", max_length=50)
    event_ids: List[str] = Field(default_factory=list)
    item_ids: List[str] = Field(default_factory=list)
    reason: Optional[str] = Field(default=None, max_length=500)


class EmbyDeleteExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(..., max_length=64)
    executed_by: Optional[str] = Field(default=None, max_length=100)


class EmbyWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    event: str = Field(alias="Event")
    item: Dict[str, Any] = Field(default_factory=dict, alias="Item")
    server: Optional[Dict[str, Any]] = Field(default=None, alias="Server")
    user: Optional[Dict[str, Any]] = Field(default=None, alias="User")


def _normalize_item_type(item: Dict[str, Any]) -> str:
    value = str(item.get("Type") or item.get("ItemType") or "").strip()
    return value or "Unknown"


def _episode_aggregate_key(event_type: str, item: Dict[str, Any]) -> str:
    series_key = (
        item.get("SeriesId")
        or item.get("SeriesName")
        or item.get("ParentId")
        or item.get("Album")
        or "unknown-series"
    )
    season = item.get("ParentIndexNumber") or item.get("SeasonNumber") or "all"
    return f"episode:{event_type}:{series_key}:S{season}"


def _episode_aggregate_name(item: Dict[str, Any]) -> str:
    series_name = item.get("SeriesName") or item.get("Series") or item.get("Name") or "Episode"
    season = item.get("ParentIndexNumber") or item.get("SeasonNumber")
    if season is None:
        return str(series_name)
    return f"{series_name} - Season {season}"


def _extract_event_latency_seconds(payload: Dict[str, Any]) -> Optional[float]:
    candidates = [
        payload.get("Date"),
        payload.get("Timestamp"),
        payload.get("EventDate"),
        payload.get("EmittedAt"),
    ]
    for raw in candidates:
        if raw is None:
            continue
        if isinstance(raw, (int, float)):
            event_ts = datetime.fromtimestamp(float(raw), tz=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - event_ts).total_seconds())
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                continue
            try:
                normalized = text.replace("Z", "+00:00")
                event_dt = datetime.fromisoformat(normalized)
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)
                return max(0.0, (datetime.now(timezone.utc) - event_dt.astimezone(timezone.utc)).total_seconds())
            except Exception:
                continue
    return None


def _log_webhook_event(
    db: Session,
    *,
    event_type: str,
    item: Dict[str, Any],
    payload: Dict[str, Any],
    aggregate_window_seconds: int,
) -> tuple[EmbyEventLog, bool]:
    item_type = _normalize_item_type(item)
    item_id = str(item.get("Id") or "") or None
    item_name = str(item.get("Name") or "") or None

    if item_type.lower() == "episode":
        aggregate_id = _episode_aggregate_key(event_type, item)
        threshold = datetime.utcnow() - timedelta(seconds=max(1, aggregate_window_seconds))
        existing = (
            db.query(EmbyEventLog)
            .filter(
                EmbyEventLog.event_type == event_type,
                EmbyEventLog.item_type == "Episode",
                EmbyEventLog.item_id == aggregate_id,
                EmbyEventLog.updated_at >= threshold,
            )
            .order_by(EmbyEventLog.updated_at.desc())
            .first()
        )
        if existing:
            merged_payload: Dict[str, Any] = {}
            if isinstance(existing.payload, dict):
                merged_payload.update(existing.payload)
            merged_payload["latest"] = payload
            merged_payload["aggregate"] = {
                "window_seconds": int(max(1, aggregate_window_seconds)),
                "count": int(existing.aggregated_count + 1),
                "key": aggregate_id,
            }
            existing.aggregated_count += 1
            existing.payload = merged_payload
            existing.item_name = _episode_aggregate_name(item)
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing, True

        row = EmbyEventLog(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            item_id=aggregate_id,
            item_name=_episode_aggregate_name(item),
            item_type="Episode",
            aggregated_count=1,
            payload={
                "latest": payload,
                "aggregate": {
                    "window_seconds": int(max(1, aggregate_window_seconds)),
                    "count": 1,
                    "key": aggregate_id,
                },
            },
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row, False

    row = EmbyEventLog(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        item_id=item_id,
        item_name=item_name,
        item_type=item_type,
        aggregated_count=1,
        payload=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, False


def _build_delete_plan_items(
    db: Session,
    *,
    event_ids: List[str],
    item_ids: List[str],
) -> List[Dict[str, Any]]:
    candidates: Dict[str, Dict[str, Any]] = {}

    if event_ids:
        logs = db.query(EmbyEventLog).filter(EmbyEventLog.event_id.in_(event_ids)).all()
        for log in logs:
            payload_item = {}
            if isinstance(log.payload, dict):
                if isinstance(log.payload.get("Item"), dict):
                    payload_item = log.payload.get("Item")  # type: ignore[assignment]
                elif isinstance(log.payload.get("latest"), dict) and isinstance(log.payload["latest"].get("Item"), dict):
                    payload_item = log.payload["latest"]["Item"]  # type: ignore[assignment]

            emby_item_id = str(payload_item.get("Id") or log.item_id or "")
            if not emby_item_id:
                continue
            candidates[emby_item_id] = {
                "event_id": log.event_id,
                "event_type": log.event_type,
                "item_name": payload_item.get("Name") or log.item_name,
                "item_type": payload_item.get("Type") or log.item_type,
            }

    for emby_item_id in item_ids:
        clean_id = str(emby_item_id).strip()
        if clean_id and clean_id not in candidates:
            candidates[clean_id] = {
                "event_id": None,
                "event_type": None,
                "item_name": None,
                "item_type": None,
            }

    plan_items: List[Dict[str, Any]] = []
    for emby_item_id in sorted(candidates.keys()):
        info = candidates[emby_item_id]
        media = db.query(EmbyMediaItem).filter(EmbyMediaItem.emby_id == emby_item_id).first()

        item_type = str((info.get("item_type") or (media.type if media else "") or "Unknown"))
        risk = "high" if item_type.lower() in {"series", "season", "movie"} else "medium"
        can_execute = bool(media and media.pickcode)
        reason = None
        if not media:
            reason = "未找到 EmbyMediaItem 映射记录"
        elif not media.pickcode:
            reason = "映射记录缺少 pickcode，无法执行云盘删除"

        plan_items.append(
            {
                "emby_item_id": emby_item_id,
                "event_id": info.get("event_id"),
                "event_type": info.get("event_type"),
                "item_name": info.get("item_name") or (media.name if media else None),
                "item_type": item_type,
                "pickcode": media.pickcode if media else None,
                "path": media.path if media else None,
                "risk_level": risk,
                "can_execute": can_execute,
                "reason": reason,
                "action": "delete_cloud_file",
            }
        )
    return plan_items


@router.get("/items/{item_id}/PlaybackInfo")
async def get_playback_info(
    item_id: str,
    request: Request,
    user_id: Optional[str] = None,
    media_source_id: Optional[str] = None,
):
    """获取 PlaybackInfo（Hook 版本）"""
    try:
        item_id = validate_identifier(item_id, "item_id")
        if user_id:
            user_id = validate_identifier(user_id, "user_id")
        if media_source_id:
            media_source_id = validate_identifier(media_source_id, "media_source_id")

        api_key = request.headers.get("X-Emby-Token") or request.query_params.get("api_key")
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing API key")

        app_config = config_service.get_config()
        emby_base_url = request.headers.get(
            "X-Emby-Server-Url",
            app_config.endpoints[0].emby_url if app_config.endpoints else "http://localhost:8096",
        )
        validate_http_url(emby_base_url, "emby_base_url")

        proxy_base_url = request.headers.get(
            "X-Proxy-Server-Url",
            f"http://{request.headers.get('host', 'localhost:8000')}",
        )
        validate_http_url(proxy_base_url, "proxy_base_url")

        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        async with EmbyProxyService(
            emby_base_url=emby_base_url,
            api_key=api_key,
            cookie=cookie,
            proxy_base_url=proxy_base_url,
        ) as proxy_service:
            return await proxy_service.proxy_playback_info(
                item_id=item_id,
                user_id=user_id or "",
                media_source_id=media_source_id,
            )
    except HTTPException:
        raise
    except InputValidationError:
        raise
    except Exception as exc:
        logger.error("Failed to get playback info: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/test-connection")
async def test_connection(
    body: Optional[EmbyTestRequest] = None,
    _auth: None = Depends(require_api_key),
):
    """
    测试 Emby 连接
    - 不传参：使用当前保存配置
    - 传参：只做临时测试，不落库
    """
    service = get_emby_service()
    kwargs: Dict[str, Any] = {"timeout": 5}
    if body:
        if body.url:
            kwargs["url"] = body.url
        if body.api_key:
            kwargs["api_key"] = body.api_key
        if body.timeout:
            kwargs["timeout"] = body.timeout
    return await service.test_connection(**kwargs)


@router.get("/libraries")
async def get_libraries():
    """获取 Emby 媒体库列表"""
    service = get_emby_service()
    if not service.is_enabled:
        raise HTTPException(status_code=400, detail="Emby 集成未启用")
    libraries = await service.get_libraries()
    return {"success": True, "libraries": libraries}


@router.post("/refresh")
async def refresh_libraries(
    background_tasks: BackgroundTasks,
    body: Optional[EmbyRefreshRequest] = None,
    _auth: None = Depends(require_api_key),
):
    """手动触发刷新（后台执行）"""
    service = get_emby_service()
    if not service.is_enabled:
        raise HTTPException(status_code=400, detail="Emby 集成未启用")
    background_tasks.add_task(service.refresh_configured_libraries, body.library_ids if body else None)
    return {"success": True, "message": "刷新任务已触发"}


@router.get("/refresh/history")
async def refresh_history(limit: int = 20):
    """获取刷新历史"""
    service = get_emby_service()
    limit = max(1, min(100, int(limit)))
    return {"success": True, "history": service.get_refresh_history(limit=limit)}


@router.get("/status")
async def get_status(probe: bool = False, probe_timeout: int = 5):
    """获取 Emby 集成状态"""
    service = get_emby_service()
    app_config = config_service.get_config()

    status = {
        "enabled": bool(service.is_enabled),
        "connected": False,
        "server_info": None,
        "configuration": {
            "enabled": bool(app_config.emby.enabled),
            "url": app_config.emby.url,
            "api_key": ("***" + app_config.emby.api_key[-4:]) if app_config.emby.api_key else "",
            "timeout": app_config.emby.timeout,
            "notify_on_complete": app_config.emby.notify_on_complete,
            "on_strm_generate": app_config.emby.refresh.on_strm_generate,
            "on_rename": app_config.emby.refresh.on_rename,
            "cron": app_config.emby.refresh.cron,
            "library_ids": app_config.emby.refresh.library_ids,
            "episode_aggregate_window_seconds": app_config.emby.refresh.episode_aggregate_window_seconds,
            "delete_execute_enabled": app_config.emby.delete_execute_enabled,
        },
    }

    if probe and service.is_enabled:
        timeout = max(1, min(30, int(probe_timeout)))
        conn = await service.test_connection(timeout=timeout)
        status["connected"] = bool(conn.get("success"))
        status["server_info"] = conn.get("server_info")

    return status


@router.post("/config")
async def update_emby_config(
    body: EmbyConfigUpdate,
    _auth: None = Depends(require_api_key),
):
    """更新 Emby 配置并持久化到 config.yaml"""
    service = get_emby_service()
    app_config = config_service.get_config()
    config_dict = app_config.model_dump()

    # 允许前端不回填 api_key：空字符串表示保持原值
    next_url = (body.url or "").strip() or (app_config.emby.url or "")
    next_api_key = (body.api_key or "").strip() or (app_config.emby.api_key or "")

    if body.enabled and not next_url:
        raise HTTPException(status_code=400, detail="启用 Emby 时必须配置 URL")
    if body.enabled and not next_api_key:
        raise HTTPException(status_code=400, detail="启用 Emby 时必须配置 API Key")

    config_dict["emby"] = {
        "enabled": bool(body.enabled),
        "url": next_url,
        "api_key": next_api_key,
        "timeout": int(body.timeout or 30),
        "notify_on_complete": bool(body.notify_on_complete),
        "delete_execute_enabled": bool(body.delete_execute_enabled),
        "refresh": {
            "on_strm_generate": bool(body.on_strm_generate),
            "on_rename": bool(body.on_rename),
            "cron": body.cron,
            "library_ids": body.library_ids or [],
            "episode_aggregate_window_seconds": int(body.episode_aggregate_window_seconds),
        },
    }

    try:
        config_service.update_config(config_dict)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"配置更新失败: {exc}") from exc

    try:
        service.configure_cron()
    except Exception as exc:
        logger.warning("Failed to configure Emby cron after config update: %s", exc)

    return {"success": True}


@router.get("/events", response_model=EmbyEventListResponse)
async def list_emby_events(
    event_type: Optional[str] = Query(default=None),
    item_type: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """事件日志查询（分页/筛选/排序）"""
    query = db.query(EmbyEventLog)

    if event_type:
        query = query.filter(EmbyEventLog.event_type == event_type.strip())
    if item_type:
        query = query.filter(EmbyEventLog.item_type == item_type.strip())
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                EmbyEventLog.event_id.ilike(like),
                EmbyEventLog.item_id.ilike(like),
                EmbyEventLog.item_name.ilike(like),
                EmbyEventLog.event_type.ilike(like),
                EmbyEventLog.item_type.ilike(like),
            )
        )

    total = query.count()
    items = (
        query.order_by(EmbyEventLog.updated_at.desc(), EmbyEventLog.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return EmbyEventListResponse(items=items, total=total)


@router.post("/delete-plan")
async def create_delete_plan(
    body: EmbyDeletePlanRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """删除联动 dry-run：仅返回删除计划，不执行真实删除"""
    if not body.event_ids and not body.item_ids:
        raise HTTPException(status_code=400, detail="event_ids 或 item_ids 至少提供一个")

    plan_items = _build_delete_plan_items(
        db,
        event_ids=body.event_ids,
        item_ids=body.item_ids,
    )
    if not plan_items:
        raise HTTPException(status_code=404, detail="未找到可生成计划的目标")

    plan = EmbyDeletePlan(
        plan_id=str(uuid.uuid4()),
        source=body.source or "manual",
        dry_run=True,
        executed=False,
        status="planned",
        request_payload=body.model_dump(),
        plan_items=plan_items,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    executable_items = sum(1 for item in plan_items if item.get("can_execute"))
    return {
        "success": True,
        "plan_id": plan.plan_id,
        "dry_run": True,
        "total_items": len(plan_items),
        "executable_items": executable_items,
        "items": plan_items,
    }


@router.post("/delete-execute")
async def execute_delete_plan(
    body: EmbyDeleteExecuteRequest,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
    collector: MetricsCollector = Depends(get_metrics_collector),
):
    """
    执行删除计划（受 feature flag 保护）

    注意：
    - 默认关闭（emby.delete_execute_enabled=false）
    - 当前执行动作仅清理本地映射记录，不触发外部真实云盘删除
    """
    app_config = config_service.get_config()
    if not app_config.emby.delete_execute_enabled:
        collector.record_metric("emby.delete.execute.blocked", 1)
        raise HTTPException(status_code=403, detail="删除执行功能未开启，请先打开 feature flag")

    plan = db.query(EmbyDeletePlan).filter(EmbyDeletePlan.plan_id == body.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="删除计划不存在")

    if plan.executed:
        items = plan.plan_items if isinstance(plan.plan_items, list) else []
        executed_items = sum(1 for item in items if item.get("execution_status") == "executed")
        skipped_items = sum(1 for item in items if item.get("execution_status") == "skipped")
        return {
            "success": True,
            "plan_id": plan.plan_id,
            "status": plan.status,
            "executed_items": executed_items,
            "skipped_items": skipped_items,
            "idempotent": True,
        }

    items: List[Dict[str, Any]] = plan.plan_items if isinstance(plan.plan_items, list) else []
    executed_count = 0
    skipped_count = 0

    for item in items:
        if not item.get("can_execute"):
            item["execution_status"] = "skipped"
            item["execution_detail"] = item.get("reason") or "目标不可执行"
            skipped_count += 1
            continue

        emby_item_id = str(item.get("emby_item_id") or "")
        media = db.query(EmbyMediaItem).filter(EmbyMediaItem.emby_id == emby_item_id).first()
        if not media:
            item["execution_status"] = "skipped"
            item["execution_detail"] = "映射记录不存在"
            skipped_count += 1
            continue

        db.delete(media)
        item["execution_status"] = "executed"
        item["execution_detail"] = "已执行本地映射清理"
        executed_count += 1

    plan.plan_items = items
    plan.dry_run = False
    plan.executed = True
    plan.executed_by = body.executed_by or "api"
    plan.executed_at = datetime.utcnow()
    if executed_count and skipped_count:
        plan.status = "partially_executed"
    elif executed_count:
        plan.status = "executed"
    else:
        plan.status = "skipped"

    db.commit()

    collector.record_metric("emby.delete.execute.warning", 1)
    collector.record_metric("emby.delete.execute.count", float(executed_count))

    return {
        "success": True,
        "plan_id": plan.plan_id,
        "status": plan.status,
        "executed_items": executed_count,
        "skipped_items": skipped_count,
    }


@router.get("/items/{item_id}")
async def get_item(item_id: str, request: Request, user_id: Optional[str] = None):
    """获取 Emby 项目信息"""
    try:
        item_id = validate_identifier(item_id, "item_id")
        if user_id:
            user_id = validate_identifier(user_id, "user_id")

        api_key = request.headers.get("X-Emby-Token") or request.query_params.get("api_key")
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing API key")

        app_config = config_service.get_config()
        emby_base_url = request.headers.get(
            "X-Emby-Server-Url",
            app_config.endpoints[0].emby_url if app_config.endpoints else "http://localhost:8096",
        )
        validate_http_url(emby_base_url, "emby_base_url")

        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        async with EmbyProxyService(emby_base_url=emby_base_url, api_key=api_key, cookie=cookie) as proxy_service:
            return await proxy_service.proxy_items_request(item_id=item_id, user_id=user_id)
    except HTTPException:
        raise
    except InputValidationError:
        raise
    except Exception as exc:
        logger.error("Failed to get item info: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/videos/{item_id}/stream")
async def stream_video(
    item_id: str,
    _request: Request,
    media_source_id: Optional[str] = None,
    static: bool = False,
    filename: Optional[str] = None,
):
    """视频流端点（307 重定向）"""
    _ = static, filename
    try:
        item_id = validate_identifier(item_id, "item_id")
        if media_source_id:
            media_source_id = validate_identifier(media_source_id, "media_source_id")

        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        file_id = media_source_id
        if not file_id:
            raise HTTPException(status_code=400, detail="Missing media_source_id")

        async with ProxyService(cookie=cookie) as service:
            redirect_url = await service.redirect_302(file_id)
            logger.info("307 redirect for item %s to %s...", item_id, redirect_url[:120])
            return RedirectResponse(url=redirect_url, status_code=307)
    except HTTPException:
        raise
    except InputValidationError:
        raise
    except Exception as exc:
        logger.error("Failed to stream video: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/videos/{item_id}/master.m3u8")
async def get_master_playlist(
    item_id: str,
    _request: Request,
    media_source_id: Optional[str] = None,
):
    """获取主播放列表（M3U8）"""
    try:
        item_id = validate_identifier(item_id, "item_id")
        if media_source_id:
            media_source_id = validate_identifier(media_source_id, "media_source_id")

        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        file_id = media_source_id
        if not file_id:
            raise HTTPException(status_code=400, detail="Missing media_source_id")

        playlist = (
            "#EXTM3U\n"
            "#EXT-X-VERSION:3\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=8000000,RESOLUTION=1920x1080\n"
            f"/api/proxy/transcoding/{file_id}\n"
        )
        return Response(
            content=playlist,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Content-Type": "application/vnd.apple.mpegurl",
                "Cache-Control": "no-cache",
            },
        )
    except HTTPException:
        raise
    except InputValidationError:
        raise
    except Exception as exc:
        logger.error("Failed to get master playlist: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/webhook")
async def emby_webhook(
    event: EmbyWebhookEvent,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    collector: MetricsCollector = Depends(get_metrics_collector),
):
    """接收 Emby Webhook 事件并入库"""
    service = get_emby_service()
    app_config = config_service.get_config()
    window_seconds = int(app_config.emby.refresh.episode_aggregate_window_seconds or 10)

    payload = event.model_dump(by_alias=True)
    row, aggregated = _log_webhook_event(
        db,
        event_type=event.event,
        item=event.item or {},
        payload=payload,
        aggregate_window_seconds=window_seconds,
    )

    collector.record_metric("emby.webhook.events_total", 1, tags={"event_type": event.event})
    latency_seconds = _extract_event_latency_seconds(payload)
    if latency_seconds is not None:
        collector.record_metric(
            "emby.webhook.event_latency_seconds",
            latency_seconds,
            tags={"event_type": event.event},
        )
    if aggregated:
        collector.record_metric("emby.webhook.episode_aggregated", 1, tags={"event_type": event.event})

    if event.event == "library.new":
        background_tasks.add_task(service.handle_library_new, event.item)
    elif event.event == "library.deleted":
        background_tasks.add_task(service.handle_library_deleted, event.item)

    return {
        "status": "processed",
        "event": event.event,
        "event_id": row.event_id,
        "aggregated": aggregated,
        "aggregated_count": row.aggregated_count,
    }


@router.post("/sync")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
):
    """手动触发全量同步"""
    service = get_emby_service()
    background_tasks.add_task(service.sync_library)
    return {"status": "started", "message": "Emby sync started in background"}


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_emby_request(request: Request, path: str):
    """Emby 通用反代入口（兜底）"""
    try:
        path = validate_proxy_path(path, "path")

        app_config = config_service.get_config()
        emby_base_url = request.headers.get(
            "X-Emby-Server-Url",
            app_config.endpoints[0].emby_url if app_config.endpoints else "http://localhost:8096",
        )
        validate_http_url(emby_base_url, "emby_base_url")

        target_url = f"{emby_base_url}/{path}"
        query_string = str(request.query_params)
        if query_string:
            target_url = f"{target_url}?{query_string}"

        logger.debug("Proxying Emby request: %s %s", request.method, target_url)
        return {
            "message": "Emby proxy endpoint",
            "method": request.method,
            "target_url": target_url,
            "path": path,
        }
    except InputValidationError:
        raise
    except Exception as exc:
        logger.error("Failed to proxy Emby request: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
