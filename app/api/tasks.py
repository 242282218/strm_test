from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.db import get_db
from app.core.dependencies import require_api_key
from app.schemas.task import TaskCreate, TaskResponse
from app.services.task_queue_service import TaskService
from app.services.task_runner import TaskRunner
from app.core.websocket_manager import ws_manager

router = APIRouter()

def get_service(db: Session = Depends(get_db)):
    return TaskService(db)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # 保持连接，接收客户端消息（如果有的话）
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@router.post("/", response_model=TaskResponse)
def create_task(
    task: TaskCreate, 
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
    service: TaskService = Depends(get_service)
):
    """创建新任务并触发后台执行"""
    new_task = service.create_task(task)
    
    # 将任务提交到后台运行
    background_tasks.add_task(TaskRunner.run_task, new_task.id)
    
    return new_task

@router.get("/", response_model=List[TaskResponse])
def list_tasks(
    status: Optional[str] = None,
    skip: int = 0, 
    limit: int = 20, 
    service: TaskService = Depends(get_service)
):
    """获取任务列表"""
    return service.get_tasks(skip, limit, status)

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int, 
    service: TaskService = Depends(get_service)
):
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: int, 
    _auth: None = Depends(require_api_key),
    service: TaskService = Depends(get_service)
):
    """取消任务"""
    success = service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel task")
    return {"status": "success"}

@router.delete("/{task_id}")
def delete_task(
    task_id: int, 
    _auth: None = Depends(require_api_key),
    service: TaskService = Depends(get_service)
):
    """删除任务记录"""
    success = service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

@router.get("/{task_id}/logs")
def get_task_logs(
    task_id: int, 
    _auth: None = Depends(require_api_key),
    service: TaskService = Depends(get_service)
):
    """获取任务日志"""
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.logs or []
