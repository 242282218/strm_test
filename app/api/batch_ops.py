"""
批量操作 API

提供批量删除、批量更新等批量操作接口。
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import require_api_key
from app.core.logging import get_logger
from app.core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/batch", tags=["Batch Operations"])


# ==================== 请求/响应模型 ====================


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""

    ids: list[int] = Field(..., description="要删除的 ID 列表", min_length=1, max_length=1000)
    hard_delete: bool = Field(False, description="是否硬删除（跳过回收站）")


class BatchDeleteResponse(BaseModel):
    """批量删除响应"""

    deleted_count: int = Field(..., description="成功删除的数量")
    failed_count: int = Field(..., description="失败的数量")
    failed_ids: list[int] = Field(default_factory=list, description="失败的 ID 列表")


class BatchStrmDeleteRequest(BaseModel):
    """批量删除 STRM 文件请求"""

    paths: list[str] = Field(..., description="STRM 文件路径列表", min_length=1, max_length=1000)


class BatchStrmDeleteResponse(BaseModel):
    """批量删除 STRM 文件响应"""

    deleted_count: int = Field(..., description="成功删除的数量")
    failed_count: int = Field(..., description="失败的数量")
    failed_paths: list[str] = Field(default_factory=list, description="失败的路径列表")


class BatchOperationStatus(BaseModel):
    """批量操作状态"""

    operation_id: str = Field(..., description="操作 ID")
    status: Literal["pending", "processing", "completed", "failed"] = Field(..., description="操作状态")
    total: int = Field(..., description="总数量")
    processed: int = Field(..., description="已处理数量")
    success: int = Field(..., description="成功数量")
    failed: int = Field(..., description="失败数量")
    created_at: str = Field(..., description="创建时间")
    completed_at: str | None = Field(None, description="完成时间")


class BatchStrmGenerateRequest(BaseModel):
    """批量生成 STRM 文件请求"""

    files: list[dict] = Field(..., description="文件信息列表，每项包含 {'name': str, 'url': str}")
    output_dir: str = Field(..., description="输出目录")


class BatchStrmGenerateResponse(BaseModel):
    """批量生成 STRM 文件响应"""

    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    failed_files: list[dict] = Field(default_factory=list, description="失败的文件列表")


# ==================== 内存操作跟踪（生产环境应使用 Redis/数据库） ====================

_operation_status: dict[str, BatchOperationStatus] = {}


# ==================== API 端点 ====================


@router.post("/delete/strm", response_model=BatchStrmDeleteResponse)
async def batch_delete_strm(
    request: BatchStrmDeleteRequest,
    _db: AsyncSession = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    """
    批量删除 STRM 文件

    - **paths**: STRM 文件路径列表
    - 支持最多 1000 个文件
    - 返回删除结果统计
    """
    from pathlib import Path

    deleted_count = 0
    failed_count = 0
    failed_paths = []

    for path in request.paths:
        try:
            file_path = Path(path)
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                deleted_count += 1
                logger.info(f"STRM deleted: {path}")
            else:
                # 文件不存在也算成功（幂等性）
                deleted_count += 1
                logger.info(f"STRM not found (skipped): {path}")
        except Exception as e:
            failed_count += 1
            failed_paths.append(path)
            logger.error(f"Failed to delete STRM {path}: {e}")

    return BatchStrmDeleteResponse(
        deleted_count=deleted_count,
        failed_count=failed_count,
        failed_paths=failed_paths,
    )


@router.post("/strm/generate", response_model=BatchStrmGenerateResponse)
async def batch_generate_strm(
    request: BatchStrmGenerateRequest,
    _auth: None = Depends(require_api_key),
):
    """
    批量生成 STRM 文件

    - **files**: 文件信息列表，每项包含 {"name": str, "url": str}
    - **output_dir**: 输出目录
    """
    from pathlib import Path

    output_path = Path(request.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failed_count = 0
    failed_files = []

    for file_info in request.files:
        try:
            name = file_info.get("name", "")
            url = file_info.get("url", "")

            if not name or not url:
                failed_count += 1
                failed_files.append(file_info)
                continue

            strm_path = output_path / f"{name}.strm"
            with open(strm_path, "w", encoding="utf-8") as f:
                f.write(url)

            success_count += 1
            logger.info(f"STRM generated: {strm_path}")
        except Exception as e:
            failed_count += 1
            failed_files.append(file_info)
            logger.error(f"Failed to generate STRM: {e}")

    return BatchStrmGenerateResponse(
        success_count=success_count,
        failed_count=failed_count,
        failed_files=failed_files,
    )


@router.get("/status/{operation_id}", response_model=BatchOperationStatus)
async def get_batch_operation_status(operation_id: str):
    """
    获取批量操作状态

    - **operation_id**: 操作 ID
    """
    if operation_id not in _operation_status:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Operation not found")

    return _operation_status[operation_id]


# ==================== 辅助函数 ====================


def create_batch_operation(total: int) -> str:
    """创建批量操作跟踪记录"""
    import uuid
    from datetime import datetime

    operation_id = str(uuid.uuid4())
    _operation_status[operation_id] = BatchOperationStatus(
        operation_id=operation_id,
        status="pending",
        total=total,
        processed=0,
        success=0,
        failed=0,
        created_at=datetime.utcnow().isoformat(),
        completed_at=None,
    )
    return operation_id


def update_batch_operation(operation_id: str, **kwargs):
    """更新批量操作状态"""
    if operation_id in _operation_status:
        status = _operation_status[operation_id]
        for key, value in kwargs.items():
            if hasattr(status, key):
                setattr(status, key, value)


def complete_batch_operation(operation_id: str):
    """完成批量操作"""
    from datetime import datetime

    if operation_id in _operation_status:
        status = _operation_status[operation_id]
        status.status = "completed"
        status.completed_at = datetime.utcnow().isoformat()


def fail_batch_operation(operation_id: str, error: str):
    """标记批量操作失败"""
    from datetime import datetime

    if operation_id in _operation_status:
        status = _operation_status[operation_id]
        status.status = "failed"
        status.completed_at = datetime.utcnow().isoformat()
