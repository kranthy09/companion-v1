"""
project/__init__.py - With structured logging
"""

from contextlib import asynccontextmanager
from broadcaster import Broadcast
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException

from project.config import settings
from project.config_validator import config_validator
from project.schemas.response import error_response
from project.schemas.errors import ErrorCode

broadcast = Broadcast(settings.WS_MESSAGE_QUEUE)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    # Configure structured logging
    from project.logging import configure_logging

    configure_logging()

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
        expose_headers=["Set-Cookie", "X-Request-ID"],
    )

    # Request logging middleware (FIRST - to capture all requests)
    from project.middleware.request_logger import RequestLoggerMiddleware

    app.add_middleware(RequestLoggerMiddleware)

    # Other middleware
    from project.middleware.exception_handlers import (
        exception_handler_middleware,
    )
    from project.middleware.validation import validation_middleware
    from project.middleware.rate_limiter import rate_limit_middleware
    from project.middleware.throttler import throttle_middleware
    from project.middleware.csrf import csrf_middleware

    app.middleware("http")(exception_handler_middleware)
    app.middleware("http")(validation_middleware)
    app.middleware("http")(csrf_middleware)
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(throttle_middleware)

    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                code=ErrorCode.INTERNAL_ERROR, message=str(exc.detail)
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=422,
            content=error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message="Validation error",
                meta={"errors": exc.errors()},
            ),
        )

    # Celery
    from project.celery_utils import create_celery

    app.celery_app = create_celery()

    # Register routes
    from project.api import api_v1, api_root, register_routers

    register_routers()

    app.include_router(api_root)
    app.include_router(api_v1)

    # WebSocket
    from project.ws.views import register_socketio_app

    register_socketio_app(app)

    @app.get("/")
    async def root():
        return {
            "message": "Companion API",
            "version": "1.0.0",
            "api": "/api/v1",
            "docs": "/docs",
        }

    @app.get("/api/v1/config")
    async def get_config():
        return {
            "api_version": "1.0.0",
            "websocket": {
                "url": "ws://localhost:8010",
                "protocols": ["websocket", "socketio"],
            },
            "security": {
                "csrf_enabled": True,
                "token_refresh_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            },
            "features": {
                "streaming": True,
                "ai_enhancement": True,
                "content_types": ["text", "markdown", "html"],
            },
            "limits": {
                "max_file_size": 10 * 1024 * 1024,
                "rate_limit": {
                    "requests_per_hour": 100,
                    "requests_per_minute": 20,
                },
            },
        }

    return app
