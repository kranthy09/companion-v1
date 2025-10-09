"""
project/api/__init__.py - Fixed circular import
"""

from fastapi import APIRouter

# Create routers first
api_v1 = APIRouter(prefix="/api/v1")
api_root = APIRouter()


def register_routers():
    """Import and register routers after modules are initialized"""
    from project.auth.views import auth_router
    from project.users import users_router
    from project.notes import notes_router
    from project.blog import blog_router
    from project.ollama import ollama_router
    from project.tasks import tasks_router
    from project.monitoring import monitoring_router
    from project.health import health_router
    from project.ws import ws_router
    from project.api.mcp import mcp_router  # Add this import

    # Register to v1
    api_v1.include_router(auth_router)
    api_v1.include_router(users_router)
    api_v1.include_router(notes_router)
    api_v1.include_router(blog_router)
    api_v1.include_router(ws_router)
    api_v1.include_router(ollama_router)
    api_v1.include_router(monitoring_router)
    api_v1.include_router(tasks_router)
    api_v1.include_router(mcp_router)  # Add this line

    # Health at root
    api_root.include_router(health_router)
