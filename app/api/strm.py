"""
STRM API路由
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.strm_service import StrmService
from app.core.logging import get_logger
from app.core.dependencies import get_quark_cookie, require_api_key
from app.core.validators import validate_path, InputValidationError
from app.core.constants import MAX_CONCURRENT_LIMIT, MIN_CONCURRENT_LIMIT, MAX_PATH_LENGTH

logger = get_logger(__name__)
router = APIRouter(prefix="/api/strm", tags=["STRM服务"])


@router.post("/scan")
async def scan_directory(
    remote_path: str = Query(..., min_length=1, max_length=MAX_PATH_LENGTH),
    local_path: str = Query(..., min_length=1, max_length=MAX_PATH_LENGTH),
    recursive: bool = Query(True),
    concurrent_limit: int = Query(5, ge=MIN_CONCURRENT_LIMIT, le=MAX_CONCURRENT_LIMIT),
    base_url: str = Query("http://localhost:8000", description="代理服务器基础URL"),
    strm_url_mode: str = Query("redirect", description="URL模式: redirect/stream/direct/webdav"),
    overwrite: bool = Query(False, description="是否覆盖已存在的 STRM 文件"),
    _auth: None = Depends(require_api_key),
    cookie: str = Depends(get_quark_cookie)
):
    """
    扫描目录并生成STRM

    参考: AlistAutoStrm mission.go:31-158
    """
    service = None
    try:
        remote_path = validate_path(remote_path, "remote_path", allow_absolute=True)
        local_path = validate_path(local_path, "local_path", allow_absolute=True)
        service = StrmService(
            cookie=cookie,
            recursive=recursive,
            base_url=base_url,
            strm_url_mode=strm_url_mode,
            overwrite_existing=overwrite,
        )
        result = await service.scan_directory(remote_path, local_path, concurrent_limit)
        return {
            "strms": result.get("strms", []),
            "count": result.get("generated_count", 0),
            "skipped": result.get("skipped_count", 0),
            "failed": result.get("failed_count", 0),
            "total": result.get("total_files", 0),
        }
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to scan directory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if service:
            await service.close()
