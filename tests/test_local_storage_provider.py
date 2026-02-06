import pytest
from fastapi import HTTPException

from app.services.storage.local import LocalStorageProvider


@pytest.mark.asyncio
async def test_local_storage_restricts_base_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SMART_MEDIA_LOCAL_ROOT", str(tmp_path))
    provider = LocalStorageProvider()

    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    items, total, parent = await provider.list(str(tmp_path), page=1, size=10)

    assert total == 1
    assert items[0].name == "a.txt"
    assert parent is None

    with pytest.raises(HTTPException) as exc:
        await provider.list(str(tmp_path.parent), page=1, size=10)
    assert exc.value.status_code == 403
