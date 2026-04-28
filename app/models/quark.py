"""
夸克数据模型

参考: OpenList quark_uc/types.go
"""

from pydantic import BaseModel, Field


class FileModel(BaseModel):
    """
    文件对象

    参考: OpenList quark_uc/types.go:21-45
    """

    fid: str = Field(..., alias="fid", description="文件ID")
    file_name: str = Field(..., alias="file_name", description="文件名")
    category: int = Field(..., alias="category", description="分类 (1=视频, 2=音频, 3=图片, 4=文档)")
    size: int = Field(0, alias="size", description="文件大小")
    l_created_at: int = Field(0, alias="l_created_at", description="本地创建时间")
    l_updated_at: int = Field(0, alias="l_updated_at", description="本地更新时间")
    file: bool = Field(False, alias="file", description="是否为文件 (True=文件, False=目录)")
    created_at: int = Field(0, alias="created_at", description="创建时间")
    updated_at: int = Field(0, alias="updated_at", description="更新时间")
    mime_type: str | None = Field(None, alias="mime_type", description="MIME类型")
    etag: str | None = Field(None, alias="etag", description="ETag")

    @property
    def name(self) -> str:
        """获取文件名"""
        return self.file_name

    @property
    def id(self) -> str:
        """获取文件ID"""
        return self.fid

    @property
    def is_dir(self) -> bool:
        """是否为目录"""
        return not self.file


class DownResp(BaseModel):
    """
    下载响应

    参考: OpenList quark_uc/types.go:104-138
    """

    data: list = Field(..., description="下载链接列表")


class TranscodingResp(BaseModel):
    """
    转码响应

    参考: OpenList quark_uc/types.go:140-214
    """

    data: dict = Field(..., description="转码数据")


class VideoInfo(BaseModel):
    """视频信息"""

    url: str = Field(..., description="视频URL")
    duration: int = Field(0, description="时长(秒)")
    size: int = Field(0, description="大小")


class VideoItem(BaseModel):
    """视频项"""

    resolution: str = Field(..., description="分辨率")
    video_info: VideoInfo | None = Field(None, description="视频信息")
