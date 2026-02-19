"""
夸克API路由
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
import asyncio
import uuid
from datetime import datetime, timezone

from app.services.quark_service import QuarkService
from app.services.smart_rename_service import get_smart_rename_service, SmartRenameOptions, AlgorithmType, NamingStandard
from app.services.ai_connectivity_service import get_ai_connectivity_service
from app.services.strm_generator import generate_strm_from_quark
from app.services.config_service import get_config_service
from app.services.config_service import get_config
from app.core.logging import get_logger
from app.core.dependencies import get_quark_cookie, get_only_video_flag, require_api_key
from app.core.validators import validate_identifier, validate_path, InputValidationError
from app.core.constants import MAX_PATH_LENGTH, MAX_FILES_LIMIT
import os

logger = get_logger(__name__)
router = APIRouter(prefix="/api/quark", tags=["夸克服务"])

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")


# ========== 请求/响应模型 ==========

class QuarkBrowseResponse(BaseModel):
    """浏览目录响应"""
    fid: str
    file_name: str
    pdir_fid: str
    file_type: int  # 0=文件夹, 1=文件
    size: int
    created_at: int
    updated_at: int
    category: Optional[str] = None


class QuarkSmartRenameRequest(BaseModel):
    """夸克云盘智能重命名请求"""
    pdir_fid: str = Field(..., description="目标目录ID")
    algorithm: Literal["standard", "ai_enhanced", "ai_only"] = "ai_enhanced"
    naming_standard: Literal["emby", "plex", "kodi"] = "emby"
    force_ai_parse: bool = False
    options: dict = Field(default_factory=dict)


class QuarkRenameOperation(BaseModel):
    """单个重命名操作"""
    fid: str = Field(..., description="文件ID")
    new_name: str = Field(..., description="新文件名")


class QuarkRenameExecuteRequest(BaseModel):
    """夸克云盘重命名执行请求"""
    batch_id: str = Field(..., description="批次ID")
    operations: List[QuarkRenameOperation] = Field(..., description="重命名操作列表")

# 获取配置管理器
class QuarkWorkflowTaskRequest(QuarkSmartRenameRequest):
    auto_execute: bool = Field(default=True, description="auto execute rename after preview")


config = get_config()

_cloud_workflow_tasks: Dict[str, Dict[str, Any]] = {}
_cloud_workflow_handles: Dict[str, asyncio.Task] = {}
_cloud_workflow_lock = asyncio.Lock()
_CLOUD_WORKFLOW_MAX_KEEP = 50


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_workflow_task(task_id: str, request: QuarkWorkflowTaskRequest) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "pending",
        "stage": "queued",
        "progress": 0,
        "message": "task queued",
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "request": request.model_dump(),
        "preview": None,
        "execute": None,
        "error": None,
    }


def _update_workflow_task(task: Dict[str, Any], **fields: Any) -> None:
    task.update(fields)
    task["updated_at"] = _utc_now_iso()


def _snapshot_workflow_task(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "stage": task["stage"],
        "progress": task["progress"],
        "message": task["message"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        "preview": task.get("preview"),
        "execute": task.get("execute"),
        "error": task.get("error"),
    }


def _prune_workflow_tasks() -> None:
    if len(_cloud_workflow_tasks) <= _CLOUD_WORKFLOW_MAX_KEEP:
        return

    sorted_tasks = sorted(
        _cloud_workflow_tasks.items(),
        key=lambda pair: pair[1].get("updated_at", ""),
        reverse=True,
    )
    keep_ids = {task_id for task_id, _ in sorted_tasks[:_CLOUD_WORKFLOW_MAX_KEEP]}
    for task_id in list(_cloud_workflow_tasks.keys()):
        if task_id not in keep_ids and task_id not in _cloud_workflow_handles:
            _cloud_workflow_tasks.pop(task_id, None)


async def _workflow_task_update(task_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    async with _cloud_workflow_lock:
        task = _cloud_workflow_tasks.get(task_id)
        if not task:
            return None
        _update_workflow_task(task, **fields)
        return task


def _handle_exception(e: Exception, message: str) -> HTTPException:
    """统一异常处理"""
    logger.error(f"{message}: {str(e)}")
    return HTTPException(status_code=500, detail=f"{message}: {str(e)}")


@router.get("/files/{parent}")
async def get_files(
    parent: str,
    cookie: str = None,
    only_video: bool = None,
    _cookie: str = Depends(get_quark_cookie),
    _only_video: bool = Depends(get_only_video_flag)
):
    """
    获取文件列表

    参考: OpenList quark_uc/util.go:69-111

    Args:
        parent: 父目录ID
        cookie: 夸克Cookie（可选，默认从配置文件读取）
        only_video: 是否只获取视频文件（可选，默认从配置文件读取）

    Returns:
        文件列表
    """
    service = None
    try:
        parent = validate_identifier(parent, "parent")
        # 正确处理only_video参数：如果显式传入None，使用配置文件的值
        # 如果显式传入true/false，使用传入的值
        final_only_video = only_video if only_video is not None else _only_video
        
        service = QuarkService(cookie=_cookie)
        files = await service.get_files(parent, only_video=final_only_video)
        return {"files": files, "count": len(files)}
    except InputValidationError:
        raise
    except Exception as e:
        raise _handle_exception(e, "Failed to get files")
    finally:
        if service:
            await service.close()


@router.get("/link/{file_id}")
async def get_download_link(
    file_id: str,
    cookie: str = None,
    _cookie: str = Depends(get_quark_cookie)
):
    """
    获取下载直链

    参考: OpenList quark_uc/util.go:113-137

    Args:
        file_id: 文件ID
        cookie: 夸克Cookie（可选，默认从配置文件读取）

    Returns:
        下载链接信息
    """
    service = None
    try:
        file_id = validate_identifier(file_id, "file_id")
        service = QuarkService(cookie=_cookie)
        link = await service.get_download_link(file_id)
        return {"url": link.url, "headers": link.headers}
    except InputValidationError:
        raise
    except Exception as e:
        raise _handle_exception(e, "Failed to get download link")
    finally:
        if service:
            await service.close()


@router.get("/transcoding/{file_id}")
async def get_transcoding_link(file_id: str, cookie: str = Depends(get_quark_cookie)):
    """
    获取转码直链

    参考: OpenList quark_uc/util.go:139-168

    Args:
        file_id: 文件ID
        cookie: 夸克Cookie（可选，默认从配置文件读取）

    Returns:
        转码链接信息
    """
    service = None
    try:
        file_id = validate_identifier(file_id, "file_id")
        service = QuarkService(cookie=cookie)
        link = await service.get_transcoding_link(file_id)
        return {"url": link.url, "headers": link.headers, "content_length": link.content_length}
    except InputValidationError:
        raise
    except Exception as e:
        raise _handle_exception(e, "Failed to get transcoding link")
    finally:
        if service:
            await service.close()


@router.get("/test/link")
async def test_link_endpoint():
    """
    测试直链获取端点

    用于集成测试
    """
    # 返回测试数据
    return {
        "url": "http://example.com/test.mp4",
        "headers": {
            "Cookie": "test_cookie",
            "Referer": "https://pan.quark.cn/"
        },
        "test": True
    }


@router.get("/browse")
async def browse_quark_directory(
    pdir_fid: str = Query("0", description="父目录ID，0表示根目录"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(50, ge=1, le=500, description="每页数量"),
    file_type: Optional[str] = Query(None, description="文件类型过滤：video/folder/all"),
    _cookie: str = Depends(get_quark_cookie)
):
    """
    浏览夸克云盘目录
    
    用途: 获取指定目录下的文件和文件夹列表，支持分页和类型过滤
    输入:
        - pdir_fid: 父目录ID，默认为"0"（根目录）
        - page: 页码，从1开始
        - size: 每页数量，范围1-500
        - file_type: 文件类型过滤（video/folder/all）
    输出:
        - 文件和文件夹列表，包含分页信息
    副作用: 调用夸克 API
    """
    service = None
    try:
        service = QuarkService(cookie=_cookie)
        result = await service.list_files(
            pdir_fid=pdir_fid,
            page=page,
            size=size
        )
        
        items = result.get("list", [])
        
        # 根据 file_type 过滤
        if file_type == "video":
            # 只返回视频文件
            items = [
                item for item in items
                if item.get("file_type") == 1  # 文件
                and service.is_video_file(item.get("file_name", ""))
            ]
        elif file_type == "folder":
            # 只返回文件夹
            items = [item for item in items if item.get("file_type") == 0]
        
        # 格式化响应
        formatted_items = []
        for item in items:
            formatted_items.append({
                "fid": item.get("fid", ""),
                "file_name": item.get("file_name", ""),
                "pdir_fid": item.get("pdir_fid", pdir_fid),
                "file_type": item.get("file_type", 1),
                "size": item.get("size", 0),
                "created_at": item.get("created_at", 0),
                "updated_at": item.get("updated_at", 0),
                "category": item.get("category", "")
            })
        
        return {
            "status": 200,
            "data": {
                "items": formatted_items,
                "total": result.get("metadata", {}).get("_total", len(items)),
                "page": page,
                "size": size
            }
        }
        
    except Exception as e:
        logger.error(f"Browse quark directory failed: {e}")
        raise HTTPException(status_code=500, detail=f"浏览目录失败: {str(e)}")
    finally:
        if service:
            await service.close()


@router.get("/config")
async def get_quark_config(_auth: None = Depends(require_api_key)):
    """
    获取夸克配置信息

    返回配置信息（不包含敏感数据）
    """
    try:
        config_service = get_config_service(CONFIG_PATH)
        app_config = config_service.get_config()
        quark_config = app_config.quark

        safe_config = {
            "referer": quark_config.referer,
            "root_id": quark_config.root_id,
            "only_video": quark_config.only_video,
            "cookie_configured": bool(quark_config.cookie),
        }
        return safe_config
    except InputValidationError:
        raise
    except Exception as e:
        raise _handle_exception(e, "Failed to get quark config")


@router.post("/sync")
async def sync_quark_files(
    cookie: str = None,
    root_id: str = None,
    _auth: None = Depends(require_api_key),
    output_dir: str = Query("./strm", min_length=1, max_length=MAX_PATH_LENGTH),
    only_video: bool = None,
    max_files: int = Query(50, ge=1, le=MAX_FILES_LIMIT)
):
    """
    同步夸克文件到STRM

    扫描夸克网盘文件并生成STRM文件

    Args:
        cookie: 夸克Cookie（可选，默认从配置文件读取）
        root_id: 根目录ID（可选，默认从配置文件读取）
        output_dir: STRM文件输出目录（可选，默认./strm）
        only_video: 是否只处理视频文件（可选，默认从配置文件读取）
        max_files: 最大处理文件数量（可选，默认50）

    Returns:
        同步结果
    """
    config_service = get_config_service(CONFIG_PATH)
    app_config = config_service.get_config()
    cookie = cookie or app_config.quark.cookie
    root_id = root_id or app_config.quark.root_id
    if only_video is None:
        only_video = app_config.quark.only_video

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie is required. Please provide cookie parameter or set it in config.yaml")

    output_dir = validate_path(output_dir, "output_dir", allow_absolute=True)
    root_id = validate_identifier(root_id, "root_id")

    try:
        # 调用STRM生成器
        result = await generate_strm_from_quark(
            cookie=cookie,
            output_dir=output_dir,
            root_id=root_id,
            only_video=only_video,
            max_files=max_files
        )

        return {
            "message": "Sync completed",
            "root_id": root_id,
            "output_dir": output_dir,
            "max_files": max_files,
            "result": result
        }
    except InputValidationError:
        raise
    except Exception as e:
        raise _handle_exception(e, "Failed to sync quark files")


@router.get("/ai-connectivity")
async def test_quark_smart_rename_ai_connectivity(
    timeout_seconds: int = Query(30, ge=1, le=120),
    _auth: None = Depends(require_api_key),
):
    """
    Test AI provider connectivity for cloud smart rename interface.
    Always tests kimi, deepseek and glm.
    """
    service = get_ai_connectivity_service()
    results = await service.test_providers(
        providers=("kimi", "deepseek", "glm"),
        timeout_seconds=timeout_seconds,
    )
    return {
        "success": True,
        "interface": "quark_smart_rename",
        "all_connected": all(item.get("connected") for item in results),
        "providers": results,
    }


async def _run_cloud_workflow_task(
    task_id: str,
    request: QuarkWorkflowTaskRequest,
    cookie: str,
) -> None:
    try:
        await _workflow_task_update(
            task_id,
            status="running",
            stage="preview",
            progress=5,
            message="generating preview",
        )
        preview_response = await smart_rename_cloud_files(
            request=request,
            _cookie=cookie,
            _auth=None,
        )
        preview_data = preview_response.get("data", {})

        await _workflow_task_update(
            task_id,
            stage="preview",
            progress=60,
            message=f"preview ready: {preview_data.get('total_items', 0)} items",
            preview=preview_data,
        )

        if not request.auto_execute:
            await _workflow_task_update(
                task_id,
                status="completed",
                stage="done",
                progress=100,
                message="preview completed",
            )
            return

        operations = []
        for item in preview_data.get("items", []) or []:
            fid = str(item.get("fid") or "").strip()
            new_name = str(item.get("new_name") or "").strip()
            if fid and new_name:
                operations.append(QuarkRenameOperation(fid=fid, new_name=new_name))

        if not operations:
            await _workflow_task_update(
                task_id,
                status="completed",
                stage="done",
                progress=100,
                message="no runnable operations after preview",
                execute={
                    "batch_id": preview_data.get("batch_id", ""),
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                    "results": [],
                },
            )
            return

        await _workflow_task_update(
            task_id,
            stage="execute",
            progress=70,
            message=f"executing rename for {len(operations)} items",
        )

        execute_request = QuarkRenameExecuteRequest(
            batch_id=str(preview_data.get("batch_id") or task_id),
            operations=operations,
        )
        execute_response = await execute_cloud_rename(
            request=execute_request,
            _cookie=cookie,
            _auth=None,
        )
        execute_data = execute_response.get("data", {})

        await _workflow_task_update(
            task_id,
            status="completed",
            stage="done",
            progress=100,
            message=(
                f"completed: success={execute_data.get('success', 0)}, "
                f"failed={execute_data.get('failed', 0)}, "
                f"skipped={execute_data.get('skipped', 0)}"
            ),
            execute=execute_data,
        )
    except asyncio.CancelledError:
        await _workflow_task_update(
            task_id,
            status="cancelled",
            stage="cancelled",
            message="task cancelled",
        )
        raise
    except Exception as exc:
        logger.error(f"Cloud workflow task failed: task_id={task_id}, error={exc}")
        await _workflow_task_update(
            task_id,
            status="failed",
            stage="failed",
            message="task failed",
            error=str(exc),
        )
    finally:
        async with _cloud_workflow_lock:
            _cloud_workflow_handles.pop(task_id, None)


@router.post("/smart-rename-cloud/workflow-tasks")
async def create_cloud_workflow_task(
    request: QuarkWorkflowTaskRequest,
    _cookie: str = Depends(get_quark_cookie),
    _auth: None = Depends(require_api_key),
):
    task_id = str(uuid.uuid4())
    task = _base_workflow_task(task_id, request)

    async with _cloud_workflow_lock:
        _cloud_workflow_tasks[task_id] = task
        _prune_workflow_tasks()
        handle = asyncio.create_task(_run_cloud_workflow_task(task_id, request, _cookie))
        _cloud_workflow_handles[task_id] = handle

    return _snapshot_workflow_task(task)


@router.get("/smart-rename-cloud/workflow-tasks/{task_id}")
async def get_cloud_workflow_task(
    task_id: str,
    _auth: None = Depends(require_api_key),
):
    async with _cloud_workflow_lock:
        task = _cloud_workflow_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="workflow task not found")
        return _snapshot_workflow_task(task)


@router.post("/smart-rename-cloud/workflow-tasks/{task_id}/cancel")
async def cancel_cloud_workflow_task(
    task_id: str,
    _auth: None = Depends(require_api_key),
):
    async with _cloud_workflow_lock:
        task = _cloud_workflow_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="workflow task not found")

        if task.get("status") in {"completed", "failed", "cancelled"}:
            return {"success": True, "task_id": task_id}

        _update_workflow_task(
            task,
            status="cancelled",
            stage="cancelled",
            message="cancel requested",
        )
        handle = _cloud_workflow_handles.get(task_id)
        if handle and not handle.done():
            handle.cancel()

    return {"success": True, "task_id": task_id}


@router.post("/smart-rename-cloud")
async def smart_rename_cloud_files(
    request: QuarkSmartRenameRequest,
    _cookie: str = Depends(get_quark_cookie),
    _auth: None = Depends(require_api_key)
):
    """
    智能重命名夸克云盘文件（预览）
    
    用途: 对夸克云盘中的文件进行智能重命名预览，返回解析结果和建议的新文件名
    输入:
        - pdir_fid: 目标目录ID
        - algorithm: 重命名算法（standard/ai_enhanced/ai_only）
        - naming_standard: 命名标准（emby/plex/kodi）
        - force_ai_parse: 是否强制使用AI解析
        - options: 高级选项
    输出:
        - 重命名预览结果，包含 batch_id 和文件列表
    副作用: 无（仅预览，不修改云盘文件）
    """
    quark_service = None
    try:
        # 初始化服务
        quark_service = QuarkService(cookie=_cookie)
        rename_service = get_smart_rename_service()

        use_fast_mode = bool(request.options.get("fast_mode", True))
        if use_fast_mode:
            logger.info(
                f"Cloud preview fast mode enabled: pdir_fid={request.pdir_fid}, recursive={request.options.get('recursive', True)}"
            )

            video_files = await quark_service.get_all_video_files(
                pdir_fid=request.pdir_fid,
                recursive=request.options.get("recursive", True),
                max_files=1000
            )

            if not video_files:
                return {
                    "status": 200,
                    "data": {
                        "batch_id": str(uuid.uuid4()),
                        "pdir_fid": request.pdir_fid,
                        "total_items": 0,
                        "matched_items": 0,
                        "parsed_items": 0,
                        "needs_confirmation": 0,
                        "average_confidence": 0,
                        "algorithm_used": request.algorithm,
                        "naming_standard": request.naming_standard,
                        "items": [],
                        "message": "璇ョ洰褰曚笅娌℃湁鎵惧埌瑙嗛鏂囦欢锛堝寘鍚瓙鐩綍锛?"
                    }
                }

            algorithm = AlgorithmType(request.algorithm)
            naming_standard = NamingStandard(request.naming_standard)
            from app.services.smart_rename_service import SmartRenameItem, SmartRenameOptions

            options = SmartRenameOptions(
                algorithm=algorithm,
                naming_standard=naming_standard,
                recursive=request.options.get("recursive", True),
                create_folders=request.options.get("create_folders", True),
                auto_confirm_high_confidence=request.options.get("auto_confirm_high_confidence", True),
                ai_confidence_threshold=request.options.get("ai_confidence_threshold", 0.7)
            )

            parse_concurrency = int(request.options.get("parse_concurrency", 3) or 3)
            parse_concurrency = max(1, min(parse_concurrency, 8))

            ai_timeout_seconds = int(request.options.get("ai_timeout_seconds", 6) or 6)
            ai_timeout_seconds = max(1, min(ai_timeout_seconds, 30))

            tmdb_timeout_seconds = int(request.options.get("tmdb_timeout_seconds", 6) or 6)
            tmdb_timeout_seconds = max(1, min(tmdb_timeout_seconds, 30))

            async def process_file(file_data: dict) -> SmartRenameItem:
                filename = file_data.get("file_name", "")
                fid = file_data.get("fid", "")
                parse_error: Optional[str] = None

                try:
                    parsed_info, used_algorithm, parse_confidence = await rename_service._parse_with_algorithm(
                        filename,
                        algorithm,
                        force_ai=request.force_ai_parse,
                        ai_timeout_seconds=ai_timeout_seconds,
                    )
                except Exception as exc:
                    parse_error = str(exc)
                    logger.warning(f"Cloud parse failed for fid={fid}, filename={filename}, fallback to standard: {exc}")
                    parsed_info, used_algorithm, parse_confidence = await rename_service._parse_with_algorithm(
                        filename,
                        AlgorithmType.STANDARD,
                        force_ai=False,
                    )

                tmdb_match = None
                match_confidence = 0.0
                try:
                    tmdb_match, match_confidence = await asyncio.wait_for(
                        rename_service._match_tmdb(
                            parsed_info,
                            media_type_hint=parsed_info.get("media_type")
                        ),
                        timeout=tmdb_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"TMDB match timeout for fid={fid}, filename={filename}")
                except Exception as exc:
                    logger.warning(f"TMDB match failed for fid={fid}, filename={filename}: {exc}")

                item = SmartRenameItem(
                    original_path=fid,
                    original_name=filename,
                    parsed_info=parsed_info,
                    tmdb_id=tmdb_match.get("id") if tmdb_match else None,
                    tmdb_title=tmdb_match.get("title") if tmdb_match else None,
                    tmdb_year=tmdb_match.get("year") if tmdb_match else None,
                    media_type=parsed_info.get("media_type", "unknown"),
                    season=parsed_info.get("season"),
                    episode=parsed_info.get("episode"),
                    parse_confidence=parse_confidence,
                    match_confidence=match_confidence,
                    overall_confidence=(parse_confidence + match_confidence) / 2,
                    used_algorithm=used_algorithm
                )

                new_path, new_name = rename_service._generate_new_name(item, options)
                item.new_path = new_path
                item.new_name = new_name

                if item.overall_confidence < options.ai_confidence_threshold:
                    item.needs_confirmation = True
                    item.confirmation_reason = f"缃俊搴﹁緝浣?({item.overall_confidence:.0%})"
                elif not tmdb_match:
                    item.needs_confirmation = True
                    item.confirmation_reason = "鏈壘鍒?TMDB 鍖归厤"

                if parse_error and not item.confirmation_reason:
                    item.needs_confirmation = True
                    item.confirmation_reason = "AI 瑙ｆ瀽澶辫触锛屽凡闄嶇骇涓烘爣鍑嗚В鏋?"

                return item

            items = []
            parsed_count = 0
            matched_count = 0
            needs_confirmation_count = 0

            for i in range(0, len(video_files), parse_concurrency):
                batch_files = video_files[i:i + parse_concurrency]
                batch_results = await asyncio.gather(
                    *(process_file(file_data) for file_data in batch_files),
                    return_exceptions=True,
                )

                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Cloud preview item processing failed: {result}")
                        continue

                    item = result
                    if item.tmdb_id:
                        matched_count += 1
                    else:
                        parsed_count += 1

                    if item.needs_confirmation:
                        needs_confirmation_count += 1

                    items.append(item)

            batch_id = str(uuid.uuid4())
            return {
                "status": 200,
                "data": {
                    "batch_id": batch_id,
                    "pdir_fid": request.pdir_fid,
                    "total_items": len(items),
                    "matched_items": matched_count,
                    "parsed_items": parsed_count,
                    "needs_confirmation": needs_confirmation_count,
                    "average_confidence": sum(item.overall_confidence for item in items) / len(items) if items else 0,
                    "algorithm_used": request.algorithm,
                    "naming_standard": request.naming_standard,
                    "items": [
                        {
                            "fid": item.original_path,
                            "original_name": item.original_name,
                            "new_name": item.new_name,
                            "tmdb_id": item.tmdb_id,
                            "tmdb_title": item.tmdb_title,
                            "tmdb_year": item.tmdb_year,
                            "media_type": item.media_type,
                            "season": item.season,
                            "episode": item.episode,
                            "overall_confidence": item.overall_confidence,
                            "used_algorithm": item.used_algorithm,
                            "needs_confirmation": item.needs_confirmation,
                            "confirmation_reason": item.confirmation_reason,
                            "status": "matched" if item.tmdb_id else "parsed"
                        }
                        for item in items
                    ]
                }
            }
        
        # 1. 递归获取云盘视频文件
        logger.info(f"开始扫描目录 {request.pdir_fid}，递归={request.options.get('recursive', True)}")
        video_files = await quark_service.get_all_video_files(
            pdir_fid=request.pdir_fid,
            recursive=request.options.get("recursive", True),
            max_files=1000
        )
        
        if not video_files:
            return {
                "status": 200,
                "data": {
                    "batch_id": str(uuid.uuid4()),
                    "pdir_fid": request.pdir_fid,
                    "total_items": 0,
                    "matched_items": 0,
                    "parsed_items": 0,
                    "needs_confirmation": 0,
                    "average_confidence": 0,
                    "algorithm_used": request.algorithm,
                    "naming_standard": request.naming_standard,
                    "items": [],
                    "message": "该目录下没有找到视频文件（包含子目录）"
                }
            }
        
        # 3. 解析算法和命名标准
        algorithm = AlgorithmType(request.algorithm)
        naming_standard = NamingStandard(request.naming_standard)
        
        # 4. 处理每个文件
        from app.services.smart_rename_service import SmartRenameItem, SmartRenameOptions
        
        items = []
        parsed_count = 0
        matched_count = 0
        needs_confirmation_count = 0
        
        for file_data in video_files:
            filename = file_data.get("file_name", "")
            fid = file_data.get("fid", "")
            
            # 使用智能重命名服务解析
            parsed_info, used_algorithm, parse_confidence = await rename_service._parse_with_algorithm(
                filename,
                algorithm,
                force_ai=request.force_ai_parse
            )
            
            # TMDB 匹配
            tmdb_match, match_confidence = await rename_service._match_tmdb(
                parsed_info,
                media_type_hint=parsed_info.get("media_type")
            )
            
            # 创建重命名项目
            item = SmartRenameItem(
                original_path=fid,  # 使用 fid 作为标识
                original_name=filename,
                parsed_info=parsed_info,
                tmdb_id=tmdb_match.get("id") if tmdb_match else None,
                tmdb_title=tmdb_match.get("title") if tmdb_match else None,
                tmdb_year=tmdb_match.get("year") if tmdb_match else None,
                media_type=parsed_info.get("media_type", "unknown"),
                season=parsed_info.get("season"),
                episode=parsed_info.get("episode"),
                parse_confidence=parse_confidence,
                match_confidence=match_confidence,
                overall_confidence=(parse_confidence + match_confidence) / 2,
                used_algorithm=used_algorithm
            )
            
            # 生成新文件名
            options = SmartRenameOptions(
                algorithm=algorithm,
                naming_standard=naming_standard,
                recursive=request.options.get("recursive", True),
                create_folders=request.options.get("create_folders", True),
                auto_confirm_high_confidence=request.options.get("auto_confirm_high_confidence", True),
                ai_confidence_threshold=request.options.get("ai_confidence_threshold", 0.7)
            )
            
            new_path, new_name = rename_service._generate_new_name(item, options)
            item.new_path = new_path
            item.new_name = new_name
            
            # 判断是否需要确认
            if item.overall_confidence < options.ai_confidence_threshold:
                item.needs_confirmation = True
                item.confirmation_reason = f"置信度较低 ({item.overall_confidence:.0%})"
            elif not tmdb_match:
                item.needs_confirmation = True
                item.confirmation_reason = "未找到 TMDB 匹配"
            
            # 更新统计
            if tmdb_match:
                matched_count += 1
            else:
                parsed_count += 1
                
            if item.needs_confirmation:
                needs_confirmation_count += 1
            
            items.append(item)
        
        # 5. 生成 batch_id
        batch_id = str(uuid.uuid4())
        
        # 6. 返回预览结果
        return {
            "status": 200,
            "data": {
                "batch_id": batch_id,
                "pdir_fid": request.pdir_fid,
                "total_items": len(items),
                "matched_items": matched_count,
                "parsed_items": parsed_count,
                "needs_confirmation": needs_confirmation_count,
                "average_confidence": sum(item.overall_confidence for item in items) / len(items) if items else 0,
                "algorithm_used": request.algorithm,
                "naming_standard": request.naming_standard,
                "items": [
                    {
                        "fid": item.original_path,
                        "original_name": item.original_name,
                        "new_name": item.new_name,
                        "tmdb_id": item.tmdb_id,
                        "tmdb_title": item.tmdb_title,
                        "tmdb_year": item.tmdb_year,
                        "media_type": item.media_type,
                        "season": item.season,
                        "episode": item.episode,
                        "overall_confidence": item.overall_confidence,
                        "used_algorithm": item.used_algorithm,
                        "needs_confirmation": item.needs_confirmation,
                        "confirmation_reason": item.confirmation_reason,
                        "status": "matched" if item.tmdb_id else "parsed"
                    }
                    for item in items
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Smart rename cloud files failed: {e}")
        raise HTTPException(status_code=500, detail=f"智能重命名预览失败: {str(e)}")
    finally:
        if quark_service:
            await quark_service.close()


@router.post("/execute-cloud-rename")
async def execute_cloud_rename(
    request: QuarkRenameExecuteRequest,
    _cookie: str = Depends(get_quark_cookie),
    _auth: None = Depends(require_api_key)
):
    """
    执行云盘文件重命名
    
    用途: 批量执行夸克云盘文件重命名操作
    输入:
        - batch_id: 批次ID（预览时返回）
        - operations: 重命名操作列表，每个操作包含 fid 和 new_name
    输出:
        - 执行结果统计
    副作用: 修改云盘中的文件名
    """
    quark_service = None
    try:
        quark_service = QuarkService(cookie=_cookie)
        
        results = []
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        # 分批执行，避免限流
        batch_size = 10
        for i in range(0, len(request.operations), batch_size):
            batch = request.operations[i:i + batch_size]
            
            for op in batch:
                try:
                    # 调用夸克 API 重命名
                    rename_result = await quark_service.rename_file(
                        fid=op.fid,
                        new_name=op.new_name
                    )
                    status = rename_result.get("status", "success")
                    if status == "skipped":
                        skipped_count += 1
                    else:
                        success_count += 1

                    results.append({
                        "fid": op.fid,
                        "status": status,
                        "old_name": rename_result.get("old_name"),
                        "new_name": rename_result.get("file_name", op.new_name),
                        "verified": bool(rename_result.get("verified", False))
                    })
                except Exception as e:
                    logger.error(f"Rename file {op.fid} failed: {e}")
                    results.append({
                        "fid": op.fid,
                        "status": "failed",
                        "error": str(e)
                    })
                    failed_count += 1
            
            # 批次间添加延迟，避免限流
            if i + batch_size < len(request.operations):
                import asyncio
                await asyncio.sleep(0.5)
        
        return {
            "status": 200,
            "data": {
                "batch_id": request.batch_id,
                "total": len(request.operations),
                "success": success_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "results": results
            }
        }
        
    except Exception as e:
        logger.error(f"Execute cloud rename failed: {e}")
        raise HTTPException(status_code=500, detail=f"执行重命名失败: {str(e)}")
    finally:
        if quark_service:
            await quark_service.close()
