"""
project/tasks/service.py - Task management service
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from .models import TaskMetadata


class TaskService:
    """Service for managing task metadata"""

    def __init__(self, db: Session):
        self.db = db

    def create_task(
        self,
        task_id: str,
        user_id: int,
        task_type: str,
        task_name: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
    ) -> TaskMetadata:
        """Create new task metadata entry"""
        task = TaskMetadata(
            task_id=task_id,
            user_id=user_id,
            task_type=task_type,
            task_name=task_name,
            resource_type=resource_type,
            resource_id=resource_id,
            status="pending",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(
        self, task_id: str, user_id: Optional[int] = None
    ) -> Optional[TaskMetadata]:
        """Get task by ID, optionally filtered by user"""
        query = self.db.query(TaskMetadata).filter(
            TaskMetadata.task_id == task_id
        )

        if user_id:
            query = query.filter(TaskMetadata.user_id == user_id)

        return query.first()

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> Optional[TaskMetadata]:
        """Update task status and result"""
        task = self.get_task(task_id)

        if not task:
            return None

        task.status = status

        # Set timestamps based on status
        if status == "running" and not task.started_at:
            task.started_at = datetime.utcnow()

        if status in ["success", "failed"] and not task.completed_at:
            task.completed_at = datetime.utcnow()

        # Update result/error
        if result is not None:
            task.result = result

        if error is not None:
            task.error = error

        self.db.commit()
        self.db.refresh(task)
        return task

    def get_user_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskMetadata]:
        """Get tasks for a specific user"""
        query = self.db.query(TaskMetadata).filter(
            TaskMetadata.user_id == user_id
        )

        if status:
            query = query.filter(TaskMetadata.status == status)

        return (
            query.order_by(TaskMetadata.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def delete_task(self, task_id: str, user_id: int) -> bool:
        """Delete task metadata"""
        task = self.get_task(task_id, user_id)

        if not task:
            return False

        self.db.delete(task)
        self.db.commit()
        return True

    def cleanup_old_tasks(self, days: int = 7) -> int:
        """Delete completed tasks older than N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        deleted = (
            self.db.query(TaskMetadata)
            .filter(
                TaskMetadata.completed_at < cutoff,
                TaskMetadata.status.in_(["success", "failed"]),
            )
            .delete()
        )

        self.db.commit()
        return deleted

    def get_task_count(
        self, user_id: int, status: Optional[str] = None
    ) -> int:
        """Get count of user's tasks"""
        query = self.db.query(TaskMetadata).filter(
            TaskMetadata.user_id == user_id
        )

        if status:
            query = query.filter(TaskMetadata.status == status)

        return query.count()
