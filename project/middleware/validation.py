"""
project/middleware/validation.py

Input validation and sanitization middleware
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
import re
import html


class InputValidator:
    def __init__(self):
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        self.suspicious_patterns = [
            r"<script[^>]*>.*?</script>",  # XSS
            r"javascript:",
            r"data:text/html",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
        ]

    def sanitize_string(self, value: str) -> str:
        """Basic HTML escaping"""
        return html.escape(value)

    def check_suspicious_content(self, content: str) -> bool:
        """Check for suspicious patterns"""
        for pattern in self.suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False


validator = InputValidator()


async def validation_middleware(request: Request, call_next):
    """Input validation middleware"""

    # Check request size
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > validator.max_request_size:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": "Request too large"},
        )

    # Check for suspicious patterns in URL
    if validator.check_suspicious_content(str(request.url)):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Suspicious request detected"},
        )

    return await call_next(request)
