"""
project/tasks/views.py
"""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from . import tasks_router
from .service import TaskService
from .schemas import TaskResponse, TaskListResponse
from .models import TaskMetadata
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.database import get_db_session
from project.schemas.response import success_response, APIResponse
from project.celery_utils import get_task_info


@tasks_router.get("/", response_model=APIResponse[TaskListResponse])
def list_my_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """List user's tasks"""
    service = TaskService(db)
    tasks = service.get_user_tasks(current_user.id, status, limit)

    return success_response(
        data=TaskListResponse(
            tasks=[TaskResponse.model_validate(t) for t in tasks],
            total=len(tasks),
        ),
        message=f"Found {len(tasks)} tasks",
    )


@tasks_router.get("/{task_id}", response_model=APIResponse[TaskResponse])
def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get task status with live Celery sync"""
    service = TaskService(db)
    task = (
        db.query(TaskMetadata)
        .filter(
            TaskMetadata.task_id == task_id,
            TaskMetadata.user_id == current_user.id,
        )
        .first()
    )

    if not task:
        raise HTTPException(404, "Task not found")

    # Sync with Celery
    celery_info = get_task_info(task_id)
    celery_state = celery_info.get("state", "").lower()

    if celery_state and celery_state != task.status:
        service.update_task_status(
            task_id,
            celery_state,
            celery_info.get("result"),
            celery_info.get("error"),
        )
        db.refresh(task)

    return success_response(
        data=TaskResponse.model_validate(task), message="Task retrieved"
    )


@tasks_router.delete("/{task_id}")
def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Cancel and delete task"""
    task = (
        db.query(TaskMetadata)
        .filter(
            TaskMetadata.task_id == task_id,
            TaskMetadata.user_id == current_user.id,
        )
        .first()
    )

    if not task:
        raise HTTPException(404, "Task not found")

    # Revoke Celery task
    try:
        from celery import current_app

        current_app.control.revoke(task_id, terminate=True)
    except Exception:
        pass  # Best effort

    db.delete(task)
    db.commit()

    return success_response(message="Task cancelled")
