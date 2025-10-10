"""
project/auth/__init__.py
"""

from fastapi import APIRouter

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

from . import views, models  # noqa
