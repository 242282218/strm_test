from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CloudDriveBase(BaseModel):
    name: str = Field(..., description="账号名称")
    drive_type: str = Field(..., description="网盘类型: quark, 115")
    remark: str | None = None


class CloudDriveCreate(CloudDriveBase):
    cookie: str = Field(..., description="Cookie字符串")


class CloudDriveUpdate(BaseModel):
    name: str | None = None
    cookie: str | None = None
    remark: str | None = None
    status: str | None = None


class CloudDriveResponse(CloudDriveBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    last_check: datetime | None
    created_at: datetime
    updated_at: datetime
