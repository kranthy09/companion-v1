"""
companion/project/health.py

Health check endpoints for monitoring
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis
from typing import Dict

from project.database import get_db_session
from project.config import settings

health_router = APIRouter(tags=["Health"])


@health_router.get("/health")
async def health_check():
    """Basic health check - always returns OK if service is running"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "healthy", "service": "companion-api"},
    )


@health_router.get("/ready")
async def readiness_check(db: Session = Depends(get_db_session)):
    """
    Readiness check - verifies all dependencies are available
    Used by Kubernetes/load balancers to determine
    if service can handle traffic
    """
    checks: Dict[str, bool] = {}
    errors: Dict[str, str] = {}

    # Check database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        checks["database"] = False
        errors["database"] = str(e)

    # Check Redis
    try:
        r = redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        checks["redis"] = True
    except Exception as e:
        checks["redis"] = False
        errors["redis"] = str(e)

    # Overall status
    all_healthy = all(checks.values())

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if all_healthy
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "errors": errors if errors else None,
        },
    )


@health_router.get("/live")
async def liveness_check():
    """
    Liveness check - indicates if service should be restarted
    Returns failure only if service is in unrecoverable state
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "alive", "service": "companion-api"},
    )
