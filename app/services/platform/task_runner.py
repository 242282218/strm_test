import asyncio
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.core.websocket_manager import ws_manager
from app.models.task import Task


logger = get_logger(__name__)


class TaskRunner:
    """任务执行器（多 Agent 编排版）"""

    TERMINAL_STATES = {"completed", "failed", "cancelled", "partial_success"}

    @staticmethod
    def _append_log(
        task: Task,
        db: Session,
        *,
        level: str,
        message: str,
        agent: str | None = None,
        stage: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        log_entry: dict[str, Any] = {
            "ts": datetime.now().timestamp(),
            "level": level.upper(),
            "message": message,
        }
        if agent:
            log_entry["agent"] = agent
        if stage:
            log_entry["stage"] = stage
        if extra:
            log_entry.update(extra)

        current_logs = list(task.logs or [])
        current_logs.append(log_entry)
        task.logs = current_logs
        db.commit()
        return log_entry

    @staticmethod
    async def _broadcast_task_update(task: Task, payload: dict[str, Any] | None = None) -> None:
        base_payload: dict[str, Any] = {
            "type": "task_update",
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
        }
        if payload:
            base_payload.update(payload)
        await ws_manager.broadcast(base_payload)

    @staticmethod
    def _ensure_orchestration_params(task: Task) -> dict[str, Any]:
        params = dict(task.params or {})
        orchestration = dict(params.get("orchestration") or {})
        orchestration.setdefault("trace_id", f"task-{task.id}-{uuid.uuid4().hex[:8]}")
        orchestration.setdefault("max_retries", 2)
        orchestration.setdefault("planner", "planner")
        orchestration.setdefault("router", "router")
        orchestration.setdefault("worker", "worker")
        orchestration.setdefault("reviewer", "reviewer")
        params["orchestration"] = orchestration
        task.params = params
        return orchestration

    @staticmethod
    async def _check_cancelled(db: Session, task: Task) -> bool:
        db.refresh(task)
        return task.status in {"cancel_requested", "cancelled"}

    @staticmethod
    async def run_task(task_id: int):
        logger.info(f"Starting task {task_id}")
        db: Session = SessionLocal()

        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            orchestration = TaskRunner._ensure_orchestration_params(task)
            trace_id = orchestration["trace_id"]
            db.commit()

            task.started_at = datetime.now()
            task.status = "planning"
            task.progress = 3
            task.total_items = task.total_items or 0
            task.processed_items = task.processed_items or 0
            db.commit()

            first_log = TaskRunner._append_log(
                task,
                db,
                level="info",
                message=f"任务进入规划阶段，trace_id={trace_id}",
                agent=orchestration["planner"],
                stage="planning",
            )
            await TaskRunner._broadcast_task_update(
                task, {"logs": [first_log], "trace_id": trace_id, "stage": "planning"}
            )

            if await TaskRunner._check_cancelled(db, task):
                return

            # Planner
            execution_plan = {
                "task_type": task.task_type,
                "priority": task.priority,
                "steps": ["plan", "route", "execute", "review"],
            }
            plan_log = TaskRunner._append_log(
                task,
                db,
                level="info",
                message=f"规划完成：{execution_plan['steps']}",
                agent=orchestration["planner"],
                stage="planning",
            )
            task.progress = 10
            db.commit()
            await TaskRunner._broadcast_task_update(
                task, {"logs": [plan_log], "trace_id": trace_id, "stage": "planning"}
            )

            if await TaskRunner._check_cancelled(db, task):
                return

            # Router
            task.status = "running"
            task.progress = 15
            db.commit()
            route_target = "media_organizer" if task.task_type == "strm_generation" else "generic_worker"
            route_log = TaskRunner._append_log(
                task,
                db,
                level="info",
                message=f"路由完成：{task.task_type} -> {route_target}",
                agent=orchestration["router"],
                stage="routing",
            )
            await TaskRunner._broadcast_task_update(
                task, {"logs": [route_log], "trace_id": trace_id, "stage": "routing"}
            )

            if await TaskRunner._check_cancelled(db, task):
                return

            # Worker with bounded retry
            worker_result: dict[str, Any] = {"processed": 0, "generated": 0, "skipped": 0, "errors": 0}
            max_retries = max(0, int(orchestration.get("max_retries", 2)))
            attempts = max_retries + 1

            async def update_progress(progress: int, message: str, _new_logs_data: list[Any]):
                task.progress = max(task.progress or 0, min(90, progress))
                progress_log = TaskRunner._append_log(
                    task,
                    db,
                    level="info",
                    message=message,
                    agent=orchestration["worker"],
                    stage="execution",
                )
                await TaskRunner._broadcast_task_update(
                    task,
                    {"logs": [progress_log], "trace_id": trace_id, "stage": "execution"},
                )
                if await TaskRunner._check_cancelled(db, task):
                    raise asyncio.CancelledError("Task cancelled")

            last_exception: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    retry_log = TaskRunner._append_log(
                        task,
                        db,
                        level="info",
                        message=f"执行阶段开始，第 {attempt}/{attempts} 次尝试",
                        agent=orchestration["worker"],
                        stage="execution",
                    )
                    await TaskRunner._broadcast_task_update(
                        task, {"logs": [retry_log], "trace_id": trace_id, "stage": "execution"}
                    )

                    if task.task_type == "strm_generation":
                        from app.services.media.organize import MediaOrganizeService

                        service = MediaOrganizeService(db)
                        worker_result = await service.process_strm_generation(task, update_progress)
                    else:
                        total = 20
                        task.total_items = total
                        db.commit()
                        for i in range(1, total + 1):
                            if await TaskRunner._check_cancelled(db, task):
                                raise asyncio.CancelledError("Task cancelled")
                            await asyncio.sleep(0.15)
                            task.processed_items = i
                            task.progress = 15 + int((i / total) * 75)
                            db.commit()
                        worker_result = {"processed": total, "generated": total, "skipped": 0, "errors": 0}

                    last_exception = None
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    last_exception = exc
                    wait_seconds = min(2**attempt, 8)
                    err_log = TaskRunner._append_log(
                        task,
                        db,
                        level="warning",
                        message=f"执行失败（第 {attempt}/{attempts} 次）：{exc}",
                        agent=orchestration["worker"],
                        stage="execution",
                        extra={"retry_in": wait_seconds},
                    )
                    await TaskRunner._broadcast_task_update(
                        task, {"logs": [err_log], "trace_id": trace_id, "stage": "execution"}
                    )
                    if attempt < attempts:
                        await asyncio.sleep(wait_seconds)

            if last_exception:
                raise last_exception

            if await TaskRunner._check_cancelled(db, task):
                return

            # Reviewer
            task.status = "reviewing"
            task.progress = 95
            db.commit()
            review_log = TaskRunner._append_log(
                task,
                db,
                level="info",
                message="进入审核阶段，校验执行结果",
                agent=orchestration["reviewer"],
                stage="reviewing",
                extra={"result": worker_result},
            )
            await TaskRunner._broadcast_task_update(
                task, {"logs": [review_log], "trace_id": trace_id, "stage": "reviewing"}
            )

            errors = int(worker_result.get("errors", 0))
            skipped = int(worker_result.get("skipped", 0))
            if errors > 0 or skipped > 0:
                task.status = "partial_success"
                task.error_message = f"任务部分完成：errors={errors}, skipped={skipped}"
            else:
                task.status = "completed"
                task.error_message = None

            task.completed_at = datetime.now()
            task.progress = 100
            db.commit()

            done_log = TaskRunner._append_log(
                task,
                db,
                level="info",
                message=f"任务结束，最终状态={task.status}",
                agent=orchestration["reviewer"],
                stage="done",
            )
            await TaskRunner._broadcast_task_update(task, {"logs": [done_log], "trace_id": trace_id, "stage": "done"})
            logger.info(f"Task {task_id} finished with status={task.status}")

        except asyncio.CancelledError:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "cancelled"
                task.completed_at = datetime.now()
                task.error_message = "Cancelled by user"
                db.commit()
                await TaskRunner._broadcast_task_update(task, {"stage": "cancelled"})
            logger.info(f"Task {task_id} cancelled")
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now()
                db.commit()
                fail_log = TaskRunner._append_log(
                    task,
                    db,
                    level="error",
                    message=f"任务失败：{e}",
                    stage="failed",
                )
                await TaskRunner._broadcast_task_update(task, {"logs": [fail_log], "stage": "failed"})
        finally:
            db.close()
