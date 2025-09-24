from fastapi import APIRouter

notes_router = APIRouter(prefix="/notes", tags=["notes"])

from . import views, models  # noqa
