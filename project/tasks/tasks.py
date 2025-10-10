"""
project/tasks/tasks.py

Background tasks for task management
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from project.database import db_context
from project.tasks.service import TaskService
from uuid import UUID

logger = get_task_logger(__name__)


@shared_task(name="cleanup_old_tasks")
def cleanup_old_tasks(days: int = 7):
    """
    Periodic task to cleanup old completed tasks

    Args:
        days: Number of days to keep completed tasks (default: 7)
    """
    try:
        with db_context() as session:
            service = TaskService(session)
            deleted_count = service.cleanup_old_tasks(days=days)
            logger.info(f"Successfully cleaned up {deleted_count} old tasks")
            return {
                "success": True,
                "deleted_count": deleted_count,
                "days": days,
            }
    except Exception as e:
        logger.error(f"Failed to cleanup old tasks: {str(e)}")
        return {"success": False, "error": str(e)}


@shared_task(name="cleanup_user_tasks")
def cleanup_user_tasks(user_id: UUID, days: int = 30):
    """
    Cleanup tasks for a specific user older than N days

    Args:
        user_id: User ID to cleanup tasks for
        days: Number of days to keep tasks (default: 30)
    """
    try:
        with db_context() as session:
            # Custom method to cleanup by user
            from project.tasks.models import TaskMetadata
            from datetime import datetime, timedelta

            cutoff = datetime.utcnow() - timedelta(days=days)
            deleted = (
                session.query(TaskMetadata)
                .filter(
                    TaskMetadata.user_id == user_id,
                    TaskMetadata.completed_at < cutoff,
                    TaskMetadata.status.in_(["success", "failed"]),
                )
                .delete()
            )

            session.commit()

            logger.info(f"Cleaned up {deleted} tasks for user {user_id}")
            return {
                "success": True,
                "deleted_count": deleted,
                "user_id": user_id,
            }
    except Exception as e:
        logger.error(f"Failed to cleanup user tasks: {str(e)}")
        return {"success": False, "error": str(e)}
