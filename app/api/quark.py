"""
夸克API路由
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import uuid

from app.services.quark_service import QuarkService
from app.services.smart_rename_service import get_smart_rename_service, SmartRenameOptions, AlgorithmType, NamingStandard
from app.services.ai_connectivity_service import get_ai_connectivity_service
from app.services.strm_generator import generate_strm_from_quark
from app.core.config_manager import get_config
from app.core.logging import get_logger
from app.core.dependencies import get_quark_cookie, get_only_video_flag, require_api_key
from app.core.validators import validate_identifier, validate_path, InputValidationError
from app.core.constants import MAX_PATH_LENGTH, MAX_FILES_LIMIT

logger = get_logger(__name__)
router = APIRouter(prefix="/api/quark", tags=["夸克服务"])


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
config = get_config()


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
async def get_transcoding_link(file_id: str, cookie: str = None):
    """
    获取转码直链

    参考: OpenList quark_uc/util.go:139-168

    Args:
        file_id: 文件ID
        cookie: 夸克Cookie（可选，默认从配置文件读取）

    Returns:
        转码链接信息
    """
    cookie = cookie or config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie is required. Please provide cookie parameter or set it in config.yaml")

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
async def get_quark_config():
    """
    获取夸克配置信息

    返回配置信息（不包含敏感数据）
    """
    try:
        quark_config = config.get_quark_config()
        # 隐藏敏感信息
        safe_config = {
            "referer": quark_config.get("referer", "https://pan.quark.cn/"),
            "root_id": quark_config.get("root_id", "0"),
            "only_video": quark_config.get("only_video", True),
            "cookie_configured": bool(quark_config.get("cookie", ""))
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
    cookie = cookie or config.get_quark_cookie()
    root_id = root_id or config.get_quark_root_id()
    if only_video is None:
        only_video = config.get_quark_only_video()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie is required. Please provide cookie parameter or set it in config.yaml")

    output_dir = validate_path(output_dir, "output_dir")
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
    timeout_seconds: int = Query(8, ge=1, le=30),
    _auth: None = Depends(require_api_key),
):
    """
    Test AI provider connectivity for cloud smart rename interface.
    Always tests both deepseek and glm.
    """
    service = get_ai_connectivity_service()
    results = await service.test_providers(
        providers=("deepseek", "glm"),
        timeout_seconds=timeout_seconds,
    )
    return {
        "success": True,
        "interface": "quark_smart_rename",
        "all_connected": all(item.get("connected") for item in results),
        "providers": results,
    }


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
        
        # 分批执行，避免限流
        batch_size = 10
        for i in range(0, len(request.operations), batch_size):
            batch = request.operations[i:i + batch_size]
            
            for op in batch:
                try:
                    # 调用夸克 API 重命名
                    await quark_service.rename_file(
                        fid=op.fid,
                        new_name=op.new_name
                    )
                    results.append({
                        "fid": op.fid,
                        "status": "success",
                        "new_name": op.new_name
                    })
                    success_count += 1
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
                "results": results
            }
        }
        
    except Exception as e:
        logger.error(f"Execute cloud rename failed: {e}")
        raise HTTPException(status_code=500, detail=f"执行重命名失败: {str(e)}")
    finally:
        if quark_service:
            await quark_service.close()
