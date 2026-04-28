from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.quark_sdk import get_service, router


class ExplodingQuarkSDKService:
    async def get_files(self, parent: str, page_size: int, only_video: bool):
        raise RuntimeError("sdk files exploded: secret upstream url")

    async def search_files(self, keyword: str, parent: str, page_size: int):
        raise RuntimeError("sdk search exploded: secret upstream url")


class TestQuarkSDKErrorSanitization:
    def test_get_files_does_not_leak_internal_error_details(self) -> None:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_service] = lambda: ExplodingQuarkSDKService()
        client = TestClient(app)

        response = client.get("/api/quark-sdk/files/0")

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to get files"}

    def test_search_files_does_not_leak_internal_error_details(self) -> None:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_service] = lambda: ExplodingQuarkSDKService()
        client = TestClient(app)

        response = client.get("/api/quark-sdk/search", params={"keyword": "demo"})

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to search files"}
