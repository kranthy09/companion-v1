"""Optimized FastAPI Application Factory"""

from contextlib import asynccontextmanager
from broadcaster import Broadcast
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException

from project.config import settings
from project.config_validator import config_validator
from project.schemas.response import error_response
from project.schemas.errors import ErrorCode
from project.middleware.cache import cache, CacheMiddleware

broadcast = Broadcast(settings.WS_MESSAGE_QUEUE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown with cache initialization"""
    config_validator.check_and_exit_on_errors()

    # Initialize cache
    await cache.init()

    # Connect broadcast
    await broadcast.connect()

    yield

    # Cleanup
    await cache.close()
    await broadcast.disconnect()


def create_app() -> FastAPI:
    """Create optimized FastAPI application"""

    app = FastAPI(
        title="Companion API",
        version="1.0.0",
        lifespan=lifespan,
        debug=getattr(settings, "DEBUG", False),
    )

    # Configure structured logging
    from project.logging import configure_logging
    configure_logging()

    # CORS - Early in middleware stack
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
        expose_headers=["Set-Cookie", "X-Request-ID"],
    )

    # Performance monitoring - FIRST for accurate timing
    from project.middleware.performance import PerformanceMiddleware
    app.add_middleware(PerformanceMiddleware)

    # Cache middleware - SECOND for early cache hits
    app.add_middleware(CacheMiddleware)

    # Request logging
    from project.middleware.request_logger import RequestLoggerMiddleware
    app.add_middleware(RequestLoggerMiddleware)

    # Security middleware
    from project.middleware.exception_handlers import (
        exception_handler_middleware
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
                code=ErrorCode.INTERNAL_ERROR,
                message=str(exc.detail)
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
                details=exc.errors()
            ),
        )

    # Initialize Celery
    from project.celery_utils import create_celery
    app.celery_app = create_celery()

    # Register routers via API module
    from project.api import api_v1, api_root, register_routers
    register_routers()

    app.include_router(api_v1)
    app.include_router(api_root)

    return app


app = create_app()
