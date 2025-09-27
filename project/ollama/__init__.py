"""
companion/project/ollama/__init__.py

Ollama module with streaming support
"""

from fastapi import APIRouter
from .service import ollama_service
from .streaming import streaming_service

ollama_router = APIRouter(prefix="/ollama", tags=["AI Services"])

from . import views, websocket  # noqa

__all__ = ["ollama_router", "ollama_service", "streaming_service"]
