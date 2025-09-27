"""
project/middleware/csrf.py
CSRF protection middleware
"""

from fastapi import Request
from fastapi.responses import JSONResponse

CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def csrf_middleware(request: Request, call_next):
    """Validate CSRF token for state-changing requests"""

    # Skip CSRF for safe methods
    if request.method in CSRF_SAFE_METHODS:
        return await call_next(request)

    # Skip CSRF for auth endpoints (login/register set the token)
    if request.url.path.startswith(
        "/auth/login"
    ) or request.url.path.startswith("/auth/register"):
        return await call_next(request)

    # Get tokens
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_cookie = request.cookies.get("csrf_token")

    # Validate
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        return JSONResponse(
            status_code=403, content={"error": "CSRF validation failed"}
        )

    return await call_next(request)
