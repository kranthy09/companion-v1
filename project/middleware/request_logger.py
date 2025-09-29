"""
project/middleware/request_logger.py - Request ID and logging middleware
"""

import time
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Add request ID and log requests"""

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Get user ID if authenticated
        user_id = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.id

        # Log request start
        start_time = time.time()
        extra = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        }
        if user_id:
            extra["user_id"] = user_id

        logger.info("Request started", extra={"extra": extra})

        # Process request
        response = await call_next(request)

        # Log request completion
        duration = time.time() - start_time
        extra["duration_ms"] = round(duration * 1000, 2)
        extra["status_code"] = response.status_code

        logger.info("Request completed", extra={"extra": extra})

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
