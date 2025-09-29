"""
project/tasks/__init__.py
"""

from fastapi import APIRouter

tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])

from . import views, models  # noqa
