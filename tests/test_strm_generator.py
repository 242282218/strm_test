"""
STRM 生成器测试

聚焦 redirect 模式下的长期稳定 URL 生成行为。
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.media.strm_generator import STRMGenerator


class _FakeQuarkService:
    def __init__(self, cookie: str):
        self.cookie = cookie

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_generate_single_file_strm_when_redirect_mode_then_writes_stable_media_url(tmp_path, sample_cookie: str):
    with patch("app.services.media.strm_generator.QuarkService", _FakeQuarkService):
        generator = STRMGenerator(
            cookie=sample_cookie,
            output_dir=str(tmp_path),
            base_url="http://proxy.example:18097",
            strm_url_mode="redirect",
            overwrite_existing=True,
        )

        try:
            relative_path = await generator.generate_single_file_strm(
                file_id="file123",
                remote_path="Movies/Avatar (2009).mkv",
            )
        finally:
            await generator.close()

    assert relative_path == "Movies/Avatar (2009).mkv.strm"

    strm_path = Path(tmp_path) / "Movies" / "Avatar (2009).mkv.strm"
    assert strm_path.exists()
    content = strm_path.read_text(encoding="utf-8")

    assert content.startswith("http://proxy.example:18097/strm/v1/m/")
    assert "/api/proxy/redirect/file123" not in content


@pytest.mark.asyncio
async def test_generate_single_file_strm_when_webdav_mode_then_logs_do_not_leak_credentials(
    tmp_path, sample_cookie: str
) -> None:
    with patch("app.services.media.strm_generator.QuarkService", _FakeQuarkService):
        generator = STRMGenerator(
            cookie=sample_cookie,
            output_dir=str(tmp_path),
            base_url="http://media.example:8000",
            strm_url_mode="webdav",
            overwrite_existing=True,
        )

        with patch("app.services.media.strm_generator.get_config") as mock_get_config:
            mock_cfg = mock_get_config.return_value
            mock_cfg.get_webdav_config.return_value = {
                "mount_path": "/dav",
                "username": "alice",
                "password": "super-secret-password",
            }

            with patch("app.services.media.strm_generator.logger") as mock_logger:
                try:
                    await generator.generate_single_file_strm(
                        file_id="file123",
                        remote_path="Movies/Avatar (2009).mkv",
                    )
                finally:
                    await generator.close()

    logged_messages = "\n".join(str(call.args[0]) for call in mock_logger.info.call_args_list if call.args)
    assert "super-secret-password" not in logged_messages
    assert "alice:" not in logged_messages
    assert "@media.example:8000" not in logged_messages
