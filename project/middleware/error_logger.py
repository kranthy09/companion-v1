"""
project/middleware/error_logger.py

Enhanced error logging for development
"""

import logging
import traceback
import json
from datetime import datetime
from pathlib import Path


class ErrorLogger:
    def __init__(self):
        self.error_log_path = Path("logs/errors.log")
        self.error_log_path.parent.mkdir(exist_ok=True)

        # Create error-specific logger
        self.logger = logging.getLogger("companion.errors")
        handler = logging.FileHandler(self.error_log_path)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.ERROR)

    def log_error(
        self,
        error: Exception,
        request_id: str = None,
        user_id: str = None,
        endpoint: str = None,
    ):
        """Log detailed error information"""
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "request_id": request_id,
            "user_id": user_id,
            "endpoint": endpoint,
        }

        self.logger.error(json.dumps(error_data, indent=2))


# Global error logger instance
error_logger = ErrorLogger()
