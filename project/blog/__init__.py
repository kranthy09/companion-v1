"""
project/blog/__init__.py

Blog module initialization and router setup
"""

from fastapi import APIRouter

# Create router with prefix
blog_router = APIRouter(prefix="/blog", tags=["Blog"])

# Import views to register routes
from . import views, models  # noqa
