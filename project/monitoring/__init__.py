"""
companion/project/monitoring/__init__.py
Monitoring app for the project
"""

from fastapi import APIRouter

monitoring_router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

from . import views  # noqa
