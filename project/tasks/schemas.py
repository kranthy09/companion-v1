"""
project/tasks/schemas.py - Task response schemas
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class TaskResponse(BaseModel):
    """Single task response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    task_type: str
    task_name: str
    status: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskListResponse(BaseModel):
    """List of tasks"""

    tasks: List[TaskResponse]
    total: int
