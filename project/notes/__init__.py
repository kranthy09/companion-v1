"""
companion/project/notes/__init__.py
Auth App, imports notes router
"""

from fastapi import APIRouter

notes_router = APIRouter(prefix="/notes", tags=["notes"])

from . import views, models  # noqa
