"""
STRM 服务模块单元测试

测试 STRM 生成、目录扫描和路径处理
"""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.strm_service import StrmService


class TestStrmService:
    """STRM 服务测试"""

    @pytest.fixture
    def service(self, sample_cookie: str):
        """创建服务实例"""
        return StrmService(
            cookie=sample_cookie,
            recursive=True,
            base_url="http://localhost:8000",
            strm_url_mode="redirect",
            max_files=0,
            only_video=True,
            overwrite_existing=False,
        )

    def test_init(self, sample_cookie: str):
        """测试初始化"""
        service = StrmService(
            cookie=sample_cookie,
            recursive=False,
            base_url="http://custom.url",
            strm_url_mode="webdav",
            max_files=100,
            only_video=False,
            overwrite_existing=True,
        )

        assert service.cookie == sample_cookie
        assert service.recursive is False
        assert service.base_url == "http://custom.url"
        assert service.strm_url_mode == "webdav"
        assert service.max_files == 100
        assert service.only_video is False
        assert service.overwrite_existing is True

    def test_normalize_remote_path_empty(self, service):
        """测试规范化空路径"""
        result = service._normalize_remote_path("")

        assert result == "/"

    def test_normalize_remote_path_none(self, service):
        """测试规范化 None 路径"""
        result = service._normalize_remote_path(None)

        assert result == "/"

    def test_normalize_remote_path_no_leading_slash(self, service):
        """测试规范化无前导斜杠的路径"""
        result = service._normalize_remote_path("videos/movies")

        assert result == "/videos/movies"

    def test_normalize_remote_path_trailing_slash(self, service):
        """测试规范化有尾部斜杠的路径"""
        result = service._normalize_remote_path("/videos/movies/")

        assert result == "/videos/movies"

    def test_normalize_remote_path_root(self, service):
        """测试规范化根路径"""
        result = service._normalize_remote_path("/")

        assert result == "/"

    def test_normalize_remote_path_already_normalized(self, service):
        """测试已规范化的路径"""
        result = service._normalize_remote_path("/videos/movies")

        assert result == "/videos/movies"

    @pytest.mark.asyncio
    async def test_close(self, service):
        """测试关闭服务"""
        await service.close()

        assert service._generator is None


class TestStrmServiceScanDirectory:
    """STRM 服务目录扫描测试"""

    @pytest.fixture
    def service(self, sample_cookie: str):
        """创建服务实例"""
        return StrmService(
            cookie=sample_cookie,
            recursive=True,
            base_url="http://localhost:8000",
            strm_url_mode="redirect",
        )

    @pytest.fixture
    def mock_generator(self):
        """创建模拟生成器"""
        generator = AsyncMock()
        generator.generate_strm_files = AsyncMock(
            return_value={
                "files": ["movie1.strm", "movie2.strm"],
                "generated_files": 2,
                "skipped_files": 0,
                "failed_files": 0,
                "total_files": 2,
            }
        )
        generator.generate_single_file_strm = AsyncMock(return_value="single.strm")
        generator.close = AsyncMock()
        return generator

    @pytest.mark.asyncio
    async def test_scan_directory_root(self, service, mock_generator):
        """测试扫描根目录"""
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(service, "_generator", None):
            with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                MockGenerator.return_value = mock_generator

                # 模拟 ScanRecord
                with patch("app.services.strm_service.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_session.return_value = mock_db

                    with patch("app.services.strm_service.ScanRecord"):
                        result = await service.scan_directory(
                            remote_path="/", local_path=tmpdir, concurrent_limit=5
                        )

                        assert result["generated_count"] == 2
                        assert result["total_files"] == 2

    @pytest.mark.asyncio
    async def test_scan_directory_with_path(self, service, mock_generator):
        """测试扫描指定路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = AsyncMock()
            mock_file = MagicMock()
            mock_file.fid = "test_fid"
            mock_file.file_name = "test_video.mp4"
            mock_file.is_dir = True
            mock_service.get_file_by_path = AsyncMock(return_value=mock_file)

            mock_generator.service = mock_service

            with patch.object(service, "_generator", None):
                with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                    MockGenerator.return_value = mock_generator

                    with patch("app.services.strm_service.SessionLocal") as mock_session:
                        mock_db = MagicMock()
                        mock_session.return_value = mock_db

                        with patch("app.services.strm_service.ScanRecord"):
                            result = await service.scan_directory(
                                remote_path="/videos/movies", local_path=tmpdir, concurrent_limit=5
                            )

                            assert "generated_count" in result

    @pytest.mark.asyncio
    async def test_scan_directory_single_file(self, service, mock_generator):
        """测试扫描单个文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = AsyncMock()
            mock_file = MagicMock()
            mock_file.fid = "file_fid"
            mock_file.file_name = "video.mp4"
            mock_file.is_dir = False
            mock_service.get_file_by_path = AsyncMock(return_value=mock_file)
            mock_service.get_full_path_by_fid = AsyncMock(return_value="videos/video.mp4")

            mock_generator.service = mock_service

            with patch.object(service, "_generator", None):
                with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                    MockGenerator.return_value = mock_generator

                    with patch("app.services.strm_service.SessionLocal") as mock_session:
                        mock_db = MagicMock()
                        mock_session.return_value = mock_db

                        with patch("app.services.strm_service.ScanRecord"):
                            result = await service.scan_directory(
                                remote_path="/videos/video.mp4", local_path=tmpdir, concurrent_limit=5
                            )

                            assert result["total_files"] == 1
                            mock_generator.generate_single_file_strm.assert_awaited_once_with(
                                file_id="file_fid",
                                remote_path="videos/video.mp4",
                            )

    @pytest.mark.asyncio
    async def test_scan_directory_single_file_when_remote_path_is_fid_then_uses_full_path(
        self, service, mock_generator
    ):
        """测试单文件以 fid 扫描时优先使用完整远端路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = AsyncMock()
            mock_file = MagicMock()
            mock_file.fid = "file_fid"
            mock_file.file_name = "video.mp4"
            mock_file.is_dir = False
            mock_service.get_file_by_path = AsyncMock(return_value=mock_file)
            mock_service.get_full_path_by_fid = AsyncMock(return_value="videos/video.mp4")

            mock_generator.service = mock_service

            with patch.object(service, "_generator", None):
                with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                    MockGenerator.return_value = mock_generator

                    with patch("app.services.strm_service.SessionLocal") as mock_session:
                        mock_db = MagicMock()
                        mock_session.return_value = mock_db

                        with patch("app.services.strm_service.ScanRecord"):
                            result = await service.scan_directory(
                                remote_path="/file_fid", local_path=tmpdir, concurrent_limit=5
                            )

                            assert result["total_files"] == 1
                            mock_generator.generate_single_file_strm.assert_awaited_once_with(
                                file_id="file_fid",
                                remote_path="videos/video.mp4",
                            )

    @pytest.mark.asyncio
    async def test_scan_directory_not_found(self, service, mock_generator):
        """测试扫描不存在的目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = AsyncMock()
            mock_service.get_file_by_path = AsyncMock(return_value=None)
            mock_service.get_file_info = AsyncMock(return_value=None)

            mock_generator.service = mock_service

            with patch.object(service, "_generator", None):
                with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                    MockGenerator.return_value = mock_generator

                    with pytest.raises(ValueError, match="Remote path not found"):
                        await service.scan_directory(remote_path="/nonexistent", local_path=tmpdir, concurrent_limit=5)


class TestStrmServiceIntegration:
    """STRM 服务集成测试"""

    @pytest.fixture
    def service(self, sample_cookie: str):
        """创建服务实例"""
        return StrmService(
            cookie=sample_cookie,
            recursive=True,
            base_url="http://localhost:8000",
            strm_url_mode="redirect",
        )

    @pytest.mark.asyncio
    async def test_scan_triggers_emby_refresh(self, service):
        """测试扫描触发 Emby 刷新"""
        mock_generator = AsyncMock()
        mock_generator.generate_strm_files = AsyncMock(
            return_value={
                "files": [],
                "generated_files": 0,
                "skipped_files": 0,
                "failed_files": 0,
                "total_files": 0,
            }
        )
        mock_generator.close = AsyncMock()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(service, "_generator", None):
            with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                MockGenerator.return_value = mock_generator

                with patch("app.services.strm_service.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_session.return_value = mock_db

                    with patch("app.services.strm_service.ScanRecord"):
                        with patch("app.services.strm_service.get_emby_service") as mock_emby:
                            mock_emby_instance = AsyncMock()
                            mock_emby_instance.trigger_refresh_on_event = AsyncMock()
                            mock_emby.return_value = mock_emby_instance

                            await service.scan_directory(remote_path="/", local_path=tmpdir, concurrent_limit=5)

                            # 验证 Emby 刷新被触发
                            mock_emby_instance.trigger_refresh_on_event.assert_called_once_with("strm_generate")

    @pytest.mark.asyncio
    async def test_scan_handles_emby_error(self, service):
        """测试扫描处理 Emby 错误"""
        mock_generator = AsyncMock()
        mock_generator.generate_strm_files = AsyncMock(
            return_value={
                "files": [],
                "generated_files": 0,
                "skipped_files": 0,
                "failed_files": 0,
                "total_files": 0,
            }
        )
        mock_generator.close = AsyncMock()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(service, "_generator", None):
            with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                MockGenerator.return_value = mock_generator

                with patch("app.services.strm_service.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_session.return_value = mock_db

                    with patch("app.services.strm_service.ScanRecord"):
                        with patch("app.services.strm_service.get_emby_service") as mock_emby:
                            mock_emby_instance = AsyncMock()
                            mock_emby_instance.trigger_refresh_on_event = AsyncMock(
                                side_effect=Exception("Emby error")
                            )
                            mock_emby.return_value = mock_emby_instance

                            # 不应该抛出异常
                            result = await service.scan_directory(
                                remote_path="/", local_path=tmpdir, concurrent_limit=5
                            )

                            assert result is not None

    @pytest.mark.asyncio
    async def test_scan_closes_db_when_scan_record_save_fails(self, service):
        """测试保存扫描记录失败时也会关闭数据库会话"""
        mock_generator = AsyncMock()
        mock_generator.generate_strm_files = AsyncMock(
            return_value={
                "files": [],
                "generated_files": 0,
                "skipped_files": 0,
                "failed_files": 0,
                "total_files": 0,
            }
        )
        mock_generator.close = AsyncMock()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(service, "_generator", None):
            with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                MockGenerator.return_value = mock_generator

                with patch("app.services.strm_service.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_session.return_value = mock_db

                    with patch("app.services.strm_service.ScanRecord") as mock_scan_record:
                        mock_scan_record.create_or_update.side_effect = RuntimeError("db write failed")

                        with patch("app.services.strm_service.get_emby_service") as mock_emby:
                            mock_emby_instance = AsyncMock()
                            mock_emby.return_value = mock_emby_instance

                            result = await service.scan_directory(
                                remote_path="/", local_path=tmpdir, concurrent_limit=5
                            )

                            assert result is not None
                            mock_db.close.assert_called_once()


class TestStrmServiceModes:
    """STRM 服务模式测试"""

    def test_redirect_mode(self, sample_cookie: str):
        """测试重定向模式"""
        service = StrmService(
            cookie=sample_cookie,
            strm_url_mode="redirect",
        )

        assert service.strm_url_mode == "redirect"

    def test_stream_mode(self, sample_cookie: str):
        """测试流模式"""
        service = StrmService(
            cookie=sample_cookie,
            strm_url_mode="stream",
        )

        assert service.strm_url_mode == "stream"

    def test_direct_mode(self, sample_cookie: str):
        """测试直连模式"""
        service = StrmService(
            cookie=sample_cookie,
            strm_url_mode="direct",
        )

        assert service.strm_url_mode == "direct"

    def test_webdav_mode(self, sample_cookie: str):
        """测试 WebDAV 模式"""
        service = StrmService(
            cookie=sample_cookie,
            strm_url_mode="webdav",
        )

        assert service.strm_url_mode == "webdav"


class TestStrmServiceOptions:
    """STRM 服务选项测试"""

    def test_recursive_option(self, sample_cookie: str):
        """测试递归选项"""
        service = StrmService(
            cookie=sample_cookie,
            recursive=True,
        )

        assert service.recursive is True

    def test_max_files_option(self, sample_cookie: str):
        """测试最大文件数选项"""
        service = StrmService(
            cookie=sample_cookie,
            max_files=100,
        )

        assert service.max_files == 100

    def test_only_video_option(self, sample_cookie: str):
        """测试仅视频选项"""
        service = StrmService(
            cookie=sample_cookie,
            only_video=True,
        )

        assert service.only_video is True

    def test_overwrite_option(self, sample_cookie: str):
        """测试覆盖选项"""
        service = StrmService(
            cookie=sample_cookie,
            overwrite_existing=True,
        )

        assert service.overwrite_existing is True


class TestStrmServiceEdgeCases:
    """STRM 服务边界情况测试"""

    @pytest.fixture
    def service(self, sample_cookie: str):
        """创建服务实例"""
        return StrmService(cookie=sample_cookie)

    def test_empty_cookie(self):
        """测试空 Cookie"""
        service = StrmService(cookie="")

        assert service.cookie == ""

    def test_special_characters_in_base_url(self):
        """测试 Base URL 中的特殊字符"""
        service = StrmService(cookie="test", base_url="http://example.com:8080/path?query=value")

        assert "example.com" in service.base_url

    @pytest.mark.asyncio
    async def test_multiple_close_calls(self, service):
        """测试多次关闭调用"""
        await service.close()
        await service.close()  # 应该不抛出异常

        assert service._generator is None

    @pytest.mark.asyncio
    async def test_scan_with_zero_concurrent_limit(self, service):
        """测试并发限制为零"""
        mock_generator = AsyncMock()
        mock_generator.generate_strm_files = AsyncMock(
            return_value={
                "files": [],
                "generated_files": 0,
                "skipped_files": 0,
                "failed_files": 0,
                "total_files": 0,
            }
        )
        mock_generator.close = AsyncMock()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(service, "_generator", None):
            with patch("app.services.strm_service.STRMGenerator") as MockGenerator:
                MockGenerator.return_value = mock_generator

                with patch("app.services.strm_service.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_session.return_value = mock_db

                    with patch("app.services.strm_service.ScanRecord"):
                        result = await service.scan_directory(
                            remote_path="/", local_path=tmpdir, concurrent_limit=0
                        )

                        assert result is not None
