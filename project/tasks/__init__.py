"""
project/tasks/__init__.py
"""

from fastapi import APIRouter

tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])

# Import all modules to register tasks
from . import views, models, tasks  # noqa
