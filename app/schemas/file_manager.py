from enum import Enum
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field

class FileType(str, Enum):
    """文件类型枚举"""
    FILE = "file"
    FOLDER = "folder"
    LINK = "link"

class StorageType(str, Enum):
    """存储类型枚举"""
    LOCAL = "local"
    QUARK = "quark"
    ALIST = "alist"
    WEBDAV = "webdav"

class FileItem(BaseModel):
    """统三的文件/文件夹模型"""
    
    id: str = Field(..., description="唯一标识（云盘用fid，本地用路径hash/路径本身）")
    name: str = Field(..., description="文件名")
    path: str = Field(..., description="完整路径")
    parent_path: Optional[str] = Field(None, description="父目录路径")
    
    file_type: FileType = Field(..., description="文件或文件夹")
    storage_type: StorageType = Field(..., description="存储类型")
    mime_type: Optional[str] = Field(None, description="MIME类型")
    extension: Optional[str] = Field(None, description="扩展名")
    
    size: int = Field(0, description="文件大小(字节)")
    updated_at: Optional[datetime] = Field(None, description="修改时间")
    
    # 预览支持
    thumbnail: Optional[str] = Field(None, description="缩略图链接")
    preview_url: Optional[str] = Field(None, description="预览/播放链接")
    
    # 状态
    is_readable: bool = Field(True)
    is_writable: bool = Field(True)
    
    # 扩展属性
    extra: Dict[str, Any] = Field(default_factory=dict, description="特定存储的原始数据")

class BrowseRequest(BaseModel):
    """浏览目录请求"""
    path: str = Field(default="/", description="目录路径或ID")
    storage: StorageType = Field(default=StorageType.QUARK)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=100, ge=1, le=500)

class BrowseResponse(BaseModel):
    """浏览目录响应"""
    items: List[FileItem]
    total: int
    path: str
    parent_path: Optional[str] = None
    breadcrumb: List[Dict[str, str]] = Field(default_factory=list)

class FileOperationAction(str, Enum):
    RENAME = "rename"
    MOVE = "move"
    DELETE = "delete"
    MKDIR = "mkdir"

class FileOperationRequest(BaseModel):
    """文件操作请求"""
    action: FileOperationAction
    storage: StorageType
    paths: List[str] = Field(..., description="要操作的路径列表")
    target: Optional[str] = Field(None, description="目标目录路径")
    new_name: Optional[str] = Field(None, description="重命名后的名称")
