"""
quark_sdk集成测试

测试SDK集成功能
"""

import pytest
import pytest_asyncio
import asyncio
from app.services.quark_sdk_service import QuarkSDKService
from app.core.sdk_config import sdk_config


@pytest.fixture
def cookie():
    """测试用cookie（需要替换为有效cookie）"""
    return "test_cookie"


@pytest_asyncio.fixture
async def service(cookie):
    """创建服务实例"""
    service = QuarkSDKService(cookie=cookie)
    yield service
    await service.close()


class TestSDKAvailability:
    """测试SDK可用性"""

    def test_sdk_available(self):
        """测试SDK是否可用"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")
        assert sdk_config.is_available() is True

    def test_quark_config(self):
        """测试夸克配置"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")
        config = sdk_config.get_quark_config()
        assert config is not None


class TestQuarkSDKService:
    """测试夸克SDK服务"""

    @pytest.mark.asyncio
    async def test_get_files(self, service):
        """测试获取文件列表"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")

        files = await service.get_files(parent="0", page_size=10)
        assert isinstance(files, list)

    @pytest.mark.asyncio
    async def test_get_download_link_invalid_file(self, service):
        """测试获取无效文件的下载链接"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")

        link = await service.get_download_link("invalid_file_id")
        assert link is None

    @pytest.mark.asyncio
    async def test_get_transcoding_link_invalid_file(self, service):
        """测试获取无效文件的转码链接"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")

        link = await service.get_transcoding_link("invalid_file_id")
        assert link is None


class TestSearchService:
    """测试搜索服务"""

    @pytest.mark.asyncio
    async def test_search_service_creation(self):
        """测试搜索服务创建"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")

        from app.services.search_service import ResourceSearchService
        service = ResourceSearchService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_search_with_invalid_keyword(self):
        """测试无效关键词搜索"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")

        from app.services.search_service import ResourceSearchService
        service = ResourceSearchService()
        result = await service.search(keyword="", page_size=10)

        assert "error" in result or result["total"] == 0


class TestRenameService:
    """测试重命名服务"""

    @pytest.mark.asyncio
    async def test_rename_service_creation(self):
        """测试重命名服务创建"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")

        from app.services.rename_service import MediaRenameService
        service = MediaRenameService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_preview_rename_invalid_path(self):
        """测试无效路径预览"""
        if not sdk_config.is_available():
            pytest.skip("SDK不可用")

        from app.services.rename_service import MediaRenameService
        service = MediaRenameService()
        result = await service.preview_rename("/nonexistent/path")

        assert "error" in result or result["tasks"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
