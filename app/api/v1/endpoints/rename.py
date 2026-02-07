from fastapi import APIRouter, Depends
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.base import BaseResponse
from app.services.rename_service import get_rename_service, RenameService
from app.core.exceptions import AppException, AppErrorCode
from app.core.validators import validate_path, InputValidationError
from app.core.dependencies import require_api_key
from app.core.constants import MAX_PATH_LENGTH, MIN_BATCH_SIZE, MAX_BATCH_SIZE, DEFAULT_BATCH_SIZE

router = APIRouter()


class RenameOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recursive: bool = True
    use_ai: bool = False
    create_folders: bool = True
    batch_size: int = Field(DEFAULT_BATCH_SIZE, ge=MIN_BATCH_SIZE, le=MAX_BATCH_SIZE)


class RenamePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_path: Optional[str] = Field(default=None, max_length=MAX_PATH_LENGTH)
    path: Optional[str] = Field(default=None, max_length=MAX_PATH_LENGTH)
    media_type: Literal["auto", "movie", "tv"] = "auto"
    recursive: bool = True
    options: Optional[RenameOptions] = None


class RenameItemResponse(BaseModel):
    original_path: str
    original_name: str
    new_path: Optional[str] = None
    new_name: Optional[str] = None
    tmdb_id: Optional[int] = None
    title: Optional[str] = None
    year: Optional[int] = None
    confidence: float = 0.0
    status: str
    error_message: Optional[str] = None


class RenamePreviewResponse(BaseModel):
    batch_id: str
    target_path: str
    total_items: int
    matched_items: int
    skipped_items: int
    items: List[RenameItemResponse]


@router.post("/preview", response_model=BaseResponse[RenamePreviewResponse])
async def preview_rename(
    request: RenamePreviewRequest,
    _auth: None = Depends(require_api_key),
    service: RenameService = Depends(get_rename_service),
):
    """Preview rename results without modifying any files."""
    try:
        target_path = request.target_path or request.path
        if not target_path:
            raise AppException(
                code=AppErrorCode.VALIDATION_ERROR,
                message="target_path or path is required",
                status_code=422,
            )
        target_path = validate_path(target_path, "target_path", allow_absolute=True)

        options = request.options.model_dump() if request.options else {}
        if "recursive" not in options:
            options["recursive"] = request.recursive

        result = await service.preview(
            target_path=target_path,
            media_type=request.media_type,
            options=options,
        )

        items = [
            RenameItemResponse(
                original_path=item.original_path,
                original_name=item.original_name,
                new_path=item.new_path,
                new_name=item.new_name,
                tmdb_id=item.tmdb_id,
                title=item.title,
                year=item.year,
                confidence=item.confidence,
                status=item.status,
                error_message=item.error_message,
            )
            for item in result.items
        ]

        response = RenamePreviewResponse(
            batch_id=result.batch_id,
            target_path=result.target_path,
            total_items=result.total_items,
            matched_items=result.matched_items,
            skipped_items=result.skipped_items,
            items=items,
        )
        return BaseResponse(data=response)
    except InputValidationError as e:
        raise AppException(
            code=AppErrorCode.VALIDATION_ERROR,
            message=str(e),
            status_code=422,
        )
    except AppException:
        raise
    except Exception as e:
        raise AppException(code=AppErrorCode.SYSTEM_ERROR, message=str(e))
