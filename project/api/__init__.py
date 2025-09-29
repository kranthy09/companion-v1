"""
project/api/__init__.py - API versioning
"""

from fastapi import APIRouter
from project.auth import auth_router
from project.users import users_router
from project.notes import notes_router
from project.tasks import tasks_router
from project.ollama import ollama_router
from project.health import health_router

# API v1 router
api_v1 = APIRouter(prefix="/api/v1")

# Register all module routers
api_v1.include_router(auth_router)
api_v1.include_router(users_router)
api_v1.include_router(notes_router)
api_v1.include_router(tasks_router)
api_v1.include_router(ollama_router)

# Health stays at root for monitoring
api_root = APIRouter()
api_root.include_router(health_router)
