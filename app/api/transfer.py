from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_api_key
from app.core.logging import get_logger
from app.services.transfer_service import TransferService


router = APIRouter(prefix="/api/transfer", tags=["Transfer"])
logger = get_logger(__name__)


class TransferRequest(BaseModel):
    drive_id: int | None = None
    share_url: str
    target_dir: str
    password: str = ""
    auto_organize: bool = False


@router.post("")
async def transfer_resource(
    req: TransferRequest,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """转存资源到网盘"""
    try:
        service = TransferService(db)
        await service.transfer_share(
            req.drive_id, req.share_url, req.target_dir, req.password, req.auto_organize, background_tasks
        )
        return {"message": "Transfer successful" + (" and organization started" if req.auto_organize else "")}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Transfer failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
