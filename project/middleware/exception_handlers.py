"""
companion/project/middleware/exception_handler.py

Global exception handler middleware
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import SQLAlchemyError
import logging
import traceback
import uuid

logger = logging.getLogger(__name__)


async def exception_handler_middleware(request: Request, call_next):
    """Global exception handler with request ID tracking"""

    # Generate request ID for tracking
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    except HTTPException as exc:
        # Let FastAPI handle HTTPExceptions normally
        logger.warning(
            f"HTTP exception: {exc.detail}",
            extra={"request_id": request_id, "status": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.detail,
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    except RequestValidationError as exc:
        logger.warning(
            f"Validation error: {exc.errors()}",
            extra={"request_id": request_id},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "Validation error",
                "detail": exc.errors(),
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    except SQLAlchemyError as exc:
        logger.error(
            f"Database error: {str(exc)}",
            extra={
                "request_id": request_id,
                "traceback": traceback.format_exc(),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Database error occurred",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    except Exception as exc:
        logger.error(
            f"Unexpected error: {str(exc)}",
            extra={
                "request_id": request_id,
                "traceback": traceback.format_exc(),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "An unexpected error occurred",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )


def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    """Custom handler for validation errors"""
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation error",
            "detail": exc.errors(),
            "request_id": request_id,
        },
    )


def http_exception_handler(request: Request, exc: HTTPException):
    """Custom handler for HTTP exceptions"""
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "request_id": request_id,
        },
    )
