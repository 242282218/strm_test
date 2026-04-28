"""
夸克 API 客户端模块单元测试

测试 API 请求、Cookie 管理和错误处理
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import pytest_asyncio

from app.services.quark_api_client import QuarkAPIClient


class TestQuarkAPIClient:
    """夸克 API 客户端测试"""

    @pytest.fixture
    def client(self, sample_cookie: str):
        """创建客户端实例"""
        return QuarkAPIClient(cookie=sample_cookie, timeout=30)

    def test_init(self, sample_cookie: str):
        """测试初始化"""
        client = QuarkAPIClient(cookie=sample_cookie, referer="https://custom.referer.com/", timeout=60)

        assert client.cookie == sample_cookie
        assert client.referer == "https://custom.referer.com/"
        assert client.base_url == "https://pan.quark.cn"
        assert client.timeout.total == 60

    def test_init_defaults(self, sample_cookie: str):
        """测试默认初始化"""
        client = QuarkAPIClient(cookie=sample_cookie)

        assert client.referer == "https://pan.quark.cn/"
        assert client.timeout.total == 30

    @pytest.mark.asyncio
    async def test_ensure_session(self, client):
        """测试确保会话初始化"""
        assert client.session is None

        await client._ensure_session()

        assert client.session is not None
        assert not client.session.closed

        await client.close()

    @pytest.mark.asyncio
    async def test_close(self, client):
        """测试关闭会话"""
        await client._ensure_session()
        await client.close()

        assert client.session.closed

    @pytest.mark.asyncio
    async def test_close_when_no_session(self, client):
        """测试无会话时关闭"""
        # 不初始化会话直接关闭
        await client.close()

        assert client.session is None


class TestQuarkAPIClientRequest:
    """夸克 API 客户端请求测试"""

    @pytest_asyncio.fixture
    async def client(self, sample_cookie: str):
        """创建客户端实例"""
        client = QuarkAPIClient(cookie=sample_cookie)
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_request_get_success(self, client):
        """测试 GET 请求成功"""
        mock_response = {"status": 200, "code": 0, "message": "success", "data": {"files": []}}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            result = await client.request("/filelist", method="GET")

            assert result == mock_response
        await client.close()

    @pytest.mark.asyncio
    async def test_request_post_success(self, client):
        """测试 POST 请求成功"""
        mock_response = {"status": 200, "code": 0, "message": "success", "data": {}}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            result = await client.request(
                "/rename", method="POST", data={"fid": "test_fid", "new_name": "new_name.mp4"}
            )

            assert result == mock_response
        await client.close()

    @pytest.mark.asyncio
    async def test_request_with_params(self, client):
        """测试带查询参数的请求"""
        mock_response = {"status": 200, "code": 0, "message": "success"}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            result = await client.request("/filelist", method="GET", params={"pdir_fid": "0", "page": "1"})

            assert result == mock_response
        await client.close()

    @pytest.mark.asyncio
    async def test_request_error_status(self, client):
        """测试错误状态码"""
        mock_response = {"status": 400, "code": 0, "message": "Bad Request"}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            with pytest.raises(Exception, match="Bad Request"):
                await client.request("/filelist")
        await client.close()

    @pytest.mark.asyncio
    async def test_request_error_code(self, client):
        """测试错误业务码"""
        mock_response = {"status": 200, "code": 500, "message": "Internal Error"}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            with pytest.raises(Exception, match="Internal Error"):
                await client.request("/filelist")
        await client.close()

    @pytest.mark.asyncio
    async def test_request_network_error(self, client):
        """测试网络错误"""
        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Network error"))
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            with pytest.raises(Exception, match="Request failed"):
                await client.request("/filelist")


class TestQuarkAPIClientCookie:
    """夸克 API 客户端 Cookie 管理测试"""

    @pytest.fixture
    def client(self, sample_cookie: str):
        """创建客户端实例"""
        return QuarkAPIClient(cookie=sample_cookie)

    def test_update_cookie(self, client):
        """测试更新 Cookie"""
        original_cookie = "key1=value1; key2=value2"
        new_cookie = client._update_cookie(original_cookie, "key1", "new_value1")

        assert "key1=new_value1" in new_cookie
        assert "key2=value2" in new_cookie

    def test_update_cookie_new_key(self, client):
        """测试添加新 Cookie 键"""
        original_cookie = "key1=value1"
        new_cookie = client._update_cookie(original_cookie, "key2", "value2")

        assert "key1=value1" in new_cookie
        assert "key2=value2" in new_cookie

    def test_update_cookie_empty(self, client):
        """测试从空 Cookie 更新"""
        new_cookie = client._update_cookie("", "key1", "value1")

        assert "key1=value1" in new_cookie

    @pytest.mark.asyncio
    async def test_cookie_update_from_response(self, client):
        """测试从响应更新 Cookie"""
        mock_response = {"status": 200, "code": 0, "message": "success"}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)

            # 模拟响应中的 Cookie
            mock_cookies = MagicMock()
            mock_cookies.__iter__ = lambda self: iter(["__puus", "__pus"])
            mock_cookies.__getitem__ = lambda self, key: MagicMock(value=f"new_{key}_value")
            mock_resp.cookies = mock_cookies

            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            original_cookie = client.cookie
            await client.request("/filelist")

            # Cookie 应该被更新
            assert client.cookie != original_cookie

        await client.close()


class TestQuarkAPIClientHeaders:
    """夸克 API 客户端请求头测试"""

    @pytest.fixture
    def client(self, sample_cookie: str):
        """创建客户端实例"""
        return QuarkAPIClient(cookie=sample_cookie)

    @pytest.mark.asyncio
    async def test_request_headers(self, client):
        """测试请求头设置"""
        mock_response = {"status": 200, "code": 0, "message": "success"}

        captured_headers = {}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}

            async def capture_request(**kwargs):
                captured_headers.update(kwargs.get("headers", {}))
                mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
                mock_resp.__aexit__ = AsyncMock()
                return mock_resp

            client.session.request = capture_request

            await client.request("/filelist")

            # 验证必要的请求头
            assert "Cookie" in captured_headers
            assert "Accept" in captured_headers
            assert "Referer" in captured_headers
            assert "User-Agent" in captured_headers

        await client.close()


class TestQuarkAPIClientQueryParams:
    """夸克 API 客户端查询参数测试"""

    @pytest.fixture
    def client(self, sample_cookie: str):
        """创建客户端实例"""
        return QuarkAPIClient(cookie=sample_cookie)

    @pytest.mark.asyncio
    async def test_default_query_params(self, client):
        """测试默认查询参数"""
        mock_response = {"status": 200, "code": 0, "message": "success"}

        captured_params = {}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}

            async def capture_request(**kwargs):
                captured_params.update(kwargs.get("params", {}))
                mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
                mock_resp.__aexit__ = AsyncMock()
                return mock_resp

            client.session.request = capture_request

            await client.request("/filelist")

            # 验证默认参数
            assert captured_params.get("pr") == "uc"
            assert captured_params.get("fr") == "pc"

        await client.close()

    @pytest.mark.asyncio
    async def test_custom_query_params(self, client):
        """测试自定义查询参数"""
        mock_response = {"status": 200, "code": 0, "message": "success"}

        captured_params = {}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}

            async def capture_request(**kwargs):
                captured_params.update(kwargs.get("params", {}))
                mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
                mock_resp.__aexit__ = AsyncMock()
                return mock_resp

            client.session.request = capture_request

            await client.request("/filelist", params={"custom_param": "value"})

            # 验证自定义参数和默认参数合并
            assert captured_params.get("pr") == "uc"
            assert captured_params.get("fr") == "pc"
            assert captured_params.get("custom_param") == "value"

        await client.close()


class TestQuarkAPIClientEdgeCases:
    """夸克 API 客户端边界情况测试"""

    @pytest.fixture
    def client(self, sample_cookie: str):
        """创建客户端实例"""
        return QuarkAPIClient(cookie=sample_cookie)

    @pytest.mark.asyncio
    async def test_empty_cookie(self):
        """测试空 Cookie"""
        client = QuarkAPIClient(cookie="")

        assert client.cookie == ""

        await client.close()

    @pytest.mark.asyncio
    async def test_special_characters_in_cookie(self):
        """测试 Cookie 中的特殊字符"""
        special_cookie = "key=value%20with%20spaces; key2=value=with=equals"
        client = QuarkAPIClient(cookie=special_cookie)

        assert client.cookie == special_cookie

        await client.close()

    @pytest.mark.asyncio
    async def test_request_timeout(self, client):
        """测试请求超时"""
        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.__aenter__ = AsyncMock(side_effect=TimeoutError())
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            with pytest.raises(Exception):
                await client.request("/filelist")

    @pytest.mark.asyncio
    async def test_json_decode_error(self, client):
        """测试 JSON 解码错误"""
        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
            mock_resp.cookies = {}
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            with pytest.raises(Exception):
                await client.request("/filelist")

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client):
        """测试并发请求"""
        mock_response = {"status": 200, "code": 0, "message": "success"}

        with patch.object(client, "_ensure_session"):
            client.session = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.cookies = {}
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()
            client.session.request = MagicMock(return_value=mock_resp)

            # 并发发送多个请求
            tasks = [client.request(f"/filelist?page={i}") for i in range(10)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            assert all(r == mock_response for r in results)

        await client.close()
