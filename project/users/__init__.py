from fastapi import APIRouter

users_router = APIRouter(prefix="/users", tags=["User Business Logic"])

# Import models and views (tasks already imported in views)
from . import views, models, tasks  # noqa
