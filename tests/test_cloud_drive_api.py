from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.cloud_drive import router


class TestCloudDriveAuthorization:
    """Cloud Drive 接口鉴权测试"""

    def test_list_drives_requires_authentication(self) -> None:
        app = FastAPI()
        app.include_router(router, prefix="/api/cloud_drive")
        client = TestClient(app)

        response = client.get("/api/cloud_drive/")

        assert response.status_code == 401

    def test_get_drive_requires_authentication(self) -> None:
        app = FastAPI()
        app.include_router(router, prefix="/api/cloud_drive")
        client = TestClient(app)

        response = client.get("/api/cloud_drive/1")

        assert response.status_code == 401
