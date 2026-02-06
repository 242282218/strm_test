import pytest

from app.services.quark_api_client_v2 import QuarkAPIClient


@pytest.mark.asyncio
async def test_get_share_token_uses_sharepage_token_endpoint():
    client = QuarkAPIClient("k=v")
    calls = []

    async def fake_request(pathname, method="GET", data=None, params=None, headers=None):
        calls.append(
            {
                "pathname": pathname,
                "method": method,
                "data": data,
                "params": params,
                "headers": headers,
            }
        )
        return {"data": {"stoken": "test_stoken"}}

    client.request = fake_request

    stoken = await client.get_share_token("abc123", "9999")

    assert stoken == "test_stoken"
    assert len(calls) == 1
    assert calls[0]["pathname"] == "/share/sharepage/token"
    assert calls[0]["method"] == "POST"
    assert calls[0]["data"] == {"pwd_id": "abc123", "passcode": "9999"}
    assert calls[0]["headers"]["Referer"] == "https://pan.quark.cn/s/abc123"
    assert calls[0]["headers"]["Origin"] == "https://pan.quark.cn"


@pytest.mark.asyncio
async def test_get_share_files_paginates_by_metadata_total():
    client = QuarkAPIClient("k=v")
    calls = []

    async def fake_request(pathname, method="GET", data=None, params=None, headers=None):
        calls.append(
            {
                "pathname": pathname,
                "method": method,
                "params": params,
                "headers": headers,
            }
        )
        page = int(params["_page"])
        if page == 1:
            return {
                "data": {"list": [{"fid": "1"}]},
                "metadata": {"_total": 2, "_count": 1},
            }
        return {
            "data": {"list": [{"fid": "2"}]},
            "metadata": {"_total": 2, "_count": 1},
        }

    client.request = fake_request

    files = await client.get_share_files("abc123", "stoken_1")

    assert [f["fid"] for f in files] == ["1", "2"]
    assert len(calls) == 2
    assert calls[0]["pathname"] == "/share/sharepage/detail"
    assert calls[0]["params"]["_page"] == "1"
    assert calls[1]["params"]["_page"] == "2"
    assert calls[0]["params"]["pwd_id"] == "abc123"
    assert calls[0]["params"]["stoken"] == "stoken_1"


@pytest.mark.asyncio
async def test_save_share_uses_sharepage_save_endpoint():
    client = QuarkAPIClient("k=v")
    calls = []

    async def fake_request(pathname, method="GET", data=None, params=None, headers=None):
        calls.append(
            {
                "pathname": pathname,
                "method": method,
                "data": data,
                "headers": headers,
            }
        )
        return {"data": {"task_id": "task_1"}}

    client.request = fake_request

    await client.save_share(
        pwd_id="abc123",
        stoken="stoken_1",
        fid_list=["fid_1", "fid_2"],
        target_fid="0",
    )

    assert len(calls) == 1
    assert calls[0]["pathname"] == "/share/sharepage/save"
    assert calls[0]["method"] == "POST"
    assert calls[0]["data"] == {
        "fid_list": ["fid_1", "fid_2"],
        "pwd_id": "abc123",
        "stoken": "stoken_1",
        "to_pdir_fid": "0",
        "pdir_fid": "0",
    }
    assert calls[0]["headers"]["Referer"] == "https://pan.quark.cn/s/abc123"
    assert calls[0]["headers"]["Origin"] == "https://pan.quark.cn"
