import pytest

from app.schemas.file_manager import FileType
from app.services.storage.quark import QuarkStorageProvider


@pytest.mark.asyncio
async def test_mkdir_normalizes_sparse_quark_response():
    class FakeQuarkService:
        async def mkdir(self, parent_fid: str, name: str):
            # Quark mkdir can return sparse data like {"fid": "..."}.
            return {"fid": "new_fid"}

    provider = QuarkStorageProvider(service=FakeQuarkService())
    item = await provider.mkdir(parent_path="0", name="test-folder")

    assert item.id == "new_fid"
    assert item.name == "test-folder"
    assert item.parent_path == "0"
    assert item.file_type == FileType.FOLDER
