"""
project/tasks/models.py - Task tracking for frontend
"""

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, Index
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from project.database import Base

if TYPE_CHECKING:
    from project.auth.models import User


class TaskMetadata(Base):
    """Track Celery tasks for user access"""

    __tablename__ = "task_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)

    # Task info
    task_type: Mapped[str] = mapped_column(
        String(50)
    )  # "enhance", "summarize"
    task_name: Mapped[str] = mapped_column(String(100))  # Human-readable
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending/running/success/failed

    # Related resource
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))  # "note"
    resource_id: Mapped[Optional[int]]

    # Results
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    # Indexes for common queries
    __table_args__ = (
        Index("idx_user_status", "user_id", "status"),
        Index("idx_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TaskMetadata(task_id='{self.task_id}', \
            type='{self.task_type}', status='{self.status}')>"
