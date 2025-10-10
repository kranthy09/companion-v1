"""
project/logging.py - Structured JSON logging with request IDs
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from uuid import UUID


class JSONFormatter(logging.Formatter):
    """Format logs as JSON with request context"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request ID if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        # Add user ID if available
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging():
    """Configure structured logging"""

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    root_logger.handlers.clear()

    # JSON handler for stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Set levels for specific loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    return root_logger


class RequestLogger:
    """Helper to log with request context"""

    def __init__(
        self, logger: logging.Logger, request_id: str, user_id: UUID = None
    ):
        self.logger = logger
        self.request_id = request_id
        self.user_id = user_id

    def _log(self, level: int, message: str, **kwargs):
        extra = {"request_id": self.request_id}
        if self.user_id:
            extra["user_id"] = self.user_id
        if kwargs:
            extra["extra"] = kwargs

        self.logger.log(level, message, extra=extra)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
