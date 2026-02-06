from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.core.db import get_db
from app.core.dependencies import require_api_key
from app.schemas.cloud_drive import CloudDriveCreate, CloudDriveUpdate, CloudDriveResponse
from app.services.cloud_drive_service import CloudDriveService

router = APIRouter()

def get_service(db: Session = Depends(get_db)):
    return CloudDriveService(db)

@router.post("/", response_model=CloudDriveResponse)
def create_drive(
    drive: CloudDriveCreate, 
    _auth: None = Depends(require_api_key),
    service: CloudDriveService = Depends(get_service)
):
    return service.create_drive(drive)

@router.get("/", response_model=List[CloudDriveResponse])
def list_drives(
    skip: int = 0, 
    limit: int = 100, 
    service: CloudDriveService = Depends(get_service)
):
    return service.get_drives(skip, limit)

@router.get("/{drive_id}", response_model=CloudDriveResponse)
def get_drive(
    drive_id: int, 
    service: CloudDriveService = Depends(get_service)
):
    drive = service.get_drive(drive_id)
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
    return drive

@router.put("/{drive_id}", response_model=CloudDriveResponse)
def update_drive(
    drive_id: int, 
    drive_update: CloudDriveUpdate, 
    _auth: None = Depends(require_api_key),
    service: CloudDriveService = Depends(get_service)
):
    drive = service.update_drive(drive_id, drive_update)
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
    return drive

@router.delete("/{drive_id}")
def delete_drive(
    drive_id: int, 
    _auth: None = Depends(require_api_key),
    service: CloudDriveService = Depends(get_service)
):
    success = service.delete_drive(drive_id)
    if not success:
        raise HTTPException(status_code=404, detail="Drive not found")
    return {"status": "success"}

@router.post("/{drive_id}/check")
async def check_drive_cookie(
    drive_id: int, 
    _auth: None = Depends(require_api_key),
    service: CloudDriveService = Depends(get_service)
):
    """检查Cookie有效性"""
    is_valid = await service.check_cookie(drive_id)
    return {"valid": is_valid}
