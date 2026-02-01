"""
STRM验证API路由

参考: alist-strm strm_validator.py
"""

from fastapi import APIRouter, HTTPException
from app.services.strm_validator import StrmValidator, ScanMode
from app.core.logging import get_logger
from typing import Optional

logger = get_logger(__name__)
router = APIRouter(prefix="/api/strm", tags=["STRM验证"])


@router.post("/validate")
async def validate_strm_files(
    target_directory: str,
    remote_base: str,
    video_formats: str,
    mode: str = "quick",
    size_threshold_mb: int = 100,
    cache_file: Optional[str] = None,
    concurrent_limit: int = 5
):
    """
    验证STRM文件

    参考: alist-strm strm_validator.py

    Args:
        target_directory: 目标目录
        remote_base: 远程根路径
        video_formats: 视频格式（逗号分隔）
        mode: 扫描模式（quick/slow）
        size_threshold_mb: 文件大小阈值（MB）
        cache_file: 缓存文件路径
        concurrent_limit: 并发限制（仅慢扫模式有效）

    Returns:
        验证结果
    """
    try:
        # 验证扫描模式
        try:
            scan_mode = ScanMode(mode.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid scan mode: {mode}")

        # 解析视频格式
        video_format_set = set(fmt.strip().lower() for fmt in video_formats.split(','))

        # 创建验证器
        validator = StrmValidator(
            target_directory=target_directory,
            remote_base=remote_base,
            video_formats=video_format_set,
            size_threshold_mb=size_threshold_mb,
            cache_file=cache_file
        )

        # 执行验证
        if scan_mode == ScanMode.QUICK:
            result = await validator.validate(scan_mode)
        else:
            result = await validator.validate(
                scan_mode,
                concurrent_limit=concurrent_limit
            )

        return result.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate STRM files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate/status")
async def get_validation_status():
    """
    获取验证状态

    Returns:
        验证状态
    """
    return {
        "status": "ready",
        "message": "STRM validation service is ready"
    }