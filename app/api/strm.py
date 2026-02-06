"""
STRM API路由
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.strm_service import StrmService
from app.core.database import resolve_db_path
from app.core.database import Database
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
    _auth: None = Depends(require_api_key),
    cookie: str = Depends(get_quark_cookie)
):
    """
    扫描目录并生成STRM

    参考: AlistAutoStrm mission.go:31-158
    """
    database = None
    service = None
    try:
        remote_path = validate_path(remote_path, "remote_path")
        local_path = validate_path(local_path, "local_path")
        database = Database(resolve_db_path())
        service = StrmService(
            cookie=cookie,
            database=database,
            recursive=recursive,
            base_url=base_url,
            strm_url_mode=strm_url_mode
        )
        strms = await service.scan_directory(remote_path, local_path, concurrent_limit)
        return {"strms": strms, "count": len(strms)}
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to scan directory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if service:
            await service.close()
        if database:
            database.close()
