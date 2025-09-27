"""
companion/project/__init__.py

Project root with validation and error logging
"""

from contextlib import asynccontextmanager
from broadcaster import Broadcast
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException

from project.config import settings

# Add validation on startup
from project.config_validator import config_validator

broadcast = Broadcast(settings.WS_MESSAGE_QUEUE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate configuration on startup
    config_validator.check_and_exit_on_errors()

    await broadcast.connect()
    yield
    await broadcast.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Companion API",
        version="1.0.0",
        lifespan=lifespan,
        debug=getattr(settings, "DEBUG", False),
    )

    from project.logging import configure_logging

    configure_logging()

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware (ORDER MATTERS)
    from project.middleware.exception_handlers import (
        exception_handler_middleware,
        validation_exception_handler,
        http_exception_handler,
    )
    from project.middleware.validation import validation_middleware
    from project.middleware.rate_limiter import rate_limit_middleware
    from project.middleware.throttler import throttle_middleware

    app.middleware("http")(exception_handler_middleware)
    app.middleware("http")(validation_middleware)  # Add this
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(throttle_middleware)

    # Exception handlers
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Initialize Celery
    from project.celery_utils import create_celery

    app.celery_app = create_celery()

    # Include routers
    from project.auth import auth_router
    from project.users import users_router
    from project.notes import notes_router
    from project.health import health_router
    from project.ollama import ollama_router
    from project.ws import ws_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(notes_router)
    app.include_router(ollama_router)
    app.include_router(ws_router)

    # Socket.IO
    from project.ws.views import register_socketio_app

    register_socketio_app(app)

    @app.get("/")
    async def root():
        return {
            "message": "Companion API",
            "version": "1.0.0",
            "docs": "/docs",
        }

    return app
