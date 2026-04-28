from app.services.media.strm_service import StrmService as MediaStrmService
from app.services.platform.task_queue import TaskService as PlatformTaskService
from app.services.platform.task_runner import TaskRunner as PlatformTaskRunner
from app.services.platform.task_scheduler import TaskScheduler as PlatformTaskScheduler
from app.services.strm_service import StrmService
from app.services.task_queue_service import TaskService
from app.services.task_runner import TaskRunner
from app.services.task_scheduler import TaskScheduler


def test_strm_service_alias_points_to_media_module() -> None:
    assert StrmService is MediaStrmService


def test_task_runner_alias_points_to_platform_module() -> None:
    assert TaskRunner is PlatformTaskRunner


def test_task_queue_alias_points_to_platform_module() -> None:
    assert TaskService is PlatformTaskService


def test_task_scheduler_alias_points_to_platform_module() -> None:
    assert TaskScheduler is PlatformTaskScheduler
