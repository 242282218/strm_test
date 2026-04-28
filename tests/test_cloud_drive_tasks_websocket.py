from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, WebSocketDisconnect

from app.api import cloud_drive, tasks
from app.core.websocket_manager import WebSocketManager
from app.schemas.cloud_drive import CloudDriveCreate, CloudDriveUpdate
from app.schemas.task import TaskCreate


def test_cloud_drive_get_service_instantiates_cloud_drive_service(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[Any] = []

    class FakeCloudDriveService:
        def __init__(self, db: Any) -> None:
            captured.append(db)

    monkeypatch.setattr(cloud_drive, "CloudDriveService", FakeCloudDriveService)

    db = object()
    service = cloud_drive.get_service(db)

    assert isinstance(service, FakeCloudDriveService)
    assert captured == [db]


def test_cloud_drive_create_and_list_use_service_results() -> None:
    class FakeService:
        @staticmethod
        def create_drive(drive: CloudDriveCreate) -> dict[str, Any]:
            return {"id": 1, "name": drive.name}

        @staticmethod
        def get_drives(skip: int, limit: int) -> list[dict[str, Any]]:
            return [{"skip": skip, "limit": limit}]

    created = cloud_drive.create_drive(
        CloudDriveCreate(name="main", drive_type="quark", cookie="cookie"),
        _auth=None,
        service=FakeService(),
    )
    listed = cloud_drive.list_drives(skip=5, limit=10, _auth=None, service=FakeService())

    assert created == {"id": 1, "name": "main"}
    assert listed == [{"skip": 5, "limit": 10}]


def test_cloud_drive_get_update_delete_handle_found_and_not_found() -> None:
    class FakeService:
        @staticmethod
        def get_drive(drive_id: int) -> dict[str, int] | None:
            return {"id": drive_id} if drive_id == 1 else None

        @staticmethod
        def update_drive(drive_id: int, payload: CloudDriveUpdate) -> dict[str, Any] | None:
            if drive_id == 1:
                return {"id": drive_id, "name": payload.name}
            return None

        @staticmethod
        def delete_drive(drive_id: int) -> bool:
            return drive_id == 1

    service = FakeService()
    assert cloud_drive.get_drive(1, _auth=None, service=service) == {"id": 1}
    assert cloud_drive.update_drive(1, CloudDriveUpdate(name="renamed"), _auth=None, service=service) == {
        "id": 1,
        "name": "renamed",
    }
    assert cloud_drive.delete_drive(1, _auth=None, service=service) == {"status": "success"}

    with pytest.raises(HTTPException) as get_exc:
        cloud_drive.get_drive(2, _auth=None, service=service)
    assert get_exc.value.status_code == 404

    with pytest.raises(HTTPException) as update_exc:
        cloud_drive.update_drive(2, CloudDriveUpdate(name="x"), _auth=None, service=service)
    assert update_exc.value.status_code == 404

    with pytest.raises(HTTPException) as delete_exc:
        cloud_drive.delete_drive(2, _auth=None, service=service)
    assert delete_exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cloud_drive_check_cookie_returns_boolean() -> None:
    class FakeService:
        @staticmethod
        async def check_cookie(drive_id: int) -> bool:
            return drive_id == 7

    assert await cloud_drive.check_drive_cookie(7, _auth=None, service=FakeService()) == {"valid": True}
    assert await cloud_drive.check_drive_cookie(8, _auth=None, service=FakeService()) == {"valid": False}


def test_task_get_service_instantiates_task_service(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[Any] = []

    class FakeTaskService:
        def __init__(self, db: Any) -> None:
            captured.append(db)

    monkeypatch.setattr(tasks, "TaskService", FakeTaskService)

    db = object()
    service = tasks.get_service(db)

    assert isinstance(service, FakeTaskService)
    assert captured == [db]


@pytest.mark.asyncio
async def test_tasks_websocket_endpoint_connects_and_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeManager:
        def __init__(self) -> None:
            self.connected: list[Any] = []
            self.disconnected: list[Any] = []

        async def connect(self, websocket: Any) -> None:
            self.connected.append(websocket)

        def disconnect(self, websocket: Any) -> None:
            self.disconnected.append(websocket)

    class FakeWebSocket:
        @staticmethod
        async def receive_text() -> str:
            raise WebSocketDisconnect(code=1000)

    manager = FakeManager()
    websocket = FakeWebSocket()
    monkeypatch.setattr(tasks, "ws_manager", manager)

    await tasks.websocket_endpoint(websocket)

    assert manager.connected == [websocket]
    assert manager.disconnected == [websocket]


def test_tasks_create_task_only_persists_task_without_background_runner() -> None:
    class FakeService:
        @staticmethod
        def create_task(task: TaskCreate) -> Any:
            return SimpleNamespace(id=123, task_type=task.task_type)

    result = tasks.create_task(
        TaskCreate(task_type="sync", priority="normal", params={"k": "v"}),
        _auth=None,
        service=FakeService(),
    )

    assert result.id == 123


def test_tasks_list_get_cancel_delete_and_logs_branches() -> None:
    existing = SimpleNamespace(id=1, logs=["line-1"])
    no_logs = SimpleNamespace(id=2, logs=None)

    class FakeService:
        @staticmethod
        def get_tasks(skip: int, limit: int, status: str | None) -> list[dict[str, Any]]:
            return [{"skip": skip, "limit": limit, "status": status}]

        @staticmethod
        def get_task(task_id: int) -> Any | None:
            if task_id == 1:
                return existing
            if task_id == 2:
                return no_logs
            return None

        @staticmethod
        def cancel_task(task_id: int) -> bool:
            return task_id == 1

        @staticmethod
        def delete_task(task_id: int) -> bool:
            return task_id == 1

    service = FakeService()

    assert tasks.list_tasks(status="done", skip=2, limit=5, service=service) == [
        {"skip": 2, "limit": 5, "status": "done"}
    ]
    assert tasks.get_task(1, service=service) is existing
    assert tasks.cancel_task(1, _auth=None, service=service) == {"status": "success"}
    assert tasks.delete_task(1, _auth=None, service=service) == {"status": "success"}
    assert tasks.get_task_logs(1, _auth=None, service=service) == ["line-1"]
    assert tasks.get_task_logs(2, _auth=None, service=service) == []

    with pytest.raises(HTTPException) as get_exc:
        tasks.get_task(3, service=service)
    assert get_exc.value.status_code == 404

    with pytest.raises(HTTPException) as cancel_exc:
        tasks.cancel_task(3, _auth=None, service=service)
    assert cancel_exc.value.status_code == 400

    with pytest.raises(HTTPException) as delete_exc:
        tasks.delete_task(3, _auth=None, service=service)
    assert delete_exc.value.status_code == 404

    with pytest.raises(HTTPException) as log_exc:
        tasks.get_task_logs(3, _auth=None, service=service)
    assert log_exc.value.status_code == 404


@pytest.mark.asyncio
async def test_websocket_manager_connect_disconnect_and_broadcast_cleanup() -> None:
    manager = WebSocketManager()

    class FakeWebSocket:
        def __init__(self, fail_send: bool = False) -> None:
            self.accepted = 0
            self.fail_send = fail_send
            self.messages: list[dict[str, Any]] = []

        async def accept(self) -> None:
            self.accepted += 1

        async def send_json(self, message: dict[str, Any]) -> None:
            if self.fail_send:
                raise RuntimeError("send failed")
            self.messages.append(message)

    ok_socket = FakeWebSocket()
    broken_socket = FakeWebSocket(fail_send=True)

    await manager.connect(ok_socket)
    await manager.connect(broken_socket)
    assert manager.active_connections == [ok_socket, broken_socket]
    assert ok_socket.accepted == 1
    assert broken_socket.accepted == 1

    await manager.broadcast({"event": "updated"})

    assert ok_socket.messages == [{"event": "updated"}]
    assert manager.active_connections == [ok_socket]

    manager.disconnect(ok_socket)
    assert manager.active_connections == []
    manager.disconnect(ok_socket)
