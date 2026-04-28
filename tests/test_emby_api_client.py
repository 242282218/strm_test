from unittest.mock import AsyncMock

import pytest

from app.services.emby_api_client import EmbyAPIClient


@pytest.mark.asyncio
async def test_get_items_when_server_requires_ids_query_then_returns_first_item():
    client = EmbyAPIClient(base_url="http://emby.example:8096", api_key="test-key")
    client._request_json = AsyncMock(
        return_value={
            "Items": [
                {
                    "Id": "145",
                    "MediaSources": [
                        {
                            "Id": "mediasource_145",
                            "Path": "http://proxy.example/api/proxy/redirect/file123",
                        }
                    ],
                }
            ]
        }
    )

    result = await client.get_items(item_id="145")

    assert result["Id"] == "145"
    client._request_json.assert_awaited_once_with(
        "GET",
        "http://emby.example:8096/Items",
        params={"Ids": "145", "Fields": "Path,MediaSources"},
    )


@pytest.mark.asyncio
async def test_get_items_when_ids_query_returns_empty_then_raises():
    client = EmbyAPIClient(base_url="http://emby.example:8096", api_key="test-key")
    client._request_json = AsyncMock(return_value={"Items": []})

    with pytest.raises(Exception, match="Emby item not found: 145"):
        await client.get_items(item_id="145")
