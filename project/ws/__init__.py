"""
companion/project/ws/__init__.py

websocket app, ws routers and module imports
"""

from fastapi import APIRouter

ws_router = APIRouter()

from . import views, utils  # noqa
